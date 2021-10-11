# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import logging
import re
import socket

from urllib.parse import urlparse
import xmlrpc.client
from flask import current_app
from werkzeug.exceptions import BadGateway, NotFound

from greenwave.cache import cached
from greenwave.request_session import get_requests_session
from greenwave.xmlrpc_server_proxy import get_server_proxy

log = logging.getLogger(__name__)

requests_session = get_requests_session()


def _requests_timeout():
    timeout = current_app.config['REQUESTS_TIMEOUT']
    if isinstance(timeout, tuple):
        return timeout[1]
    return timeout


class BaseRetriever:
    def __init__(self, ignore_ids, when, url):
        self.ignore_ids = ignore_ids
        self.url = url

        if when:
            self.since = '1900-01-01T00:00:00.000000,{}'.format(when)
        else:
            self.since = None

    def retrieve(self, *args, **kwargs):
        items = self._retrieve_all(*args, **kwargs)
        return [item for item in items if item['id'] not in self.ignore_ids]

    def _retrieve_data(self, params):
        response = self._make_request(params)
        response.raise_for_status()
        return response.json()['data']


class ResultsRetriever(BaseRetriever):
    """
    Retrieves results from cache or ResultsDB.
    """

    def __init__(self, **args):
        super().__init__(**args)
        self.cache = {}

    def _retrieve_all(self, subject, testcase=None):
        # Get test case result from cache if all test case results were already
        # retrieved for given Subject.
        cache_key = (subject.type, subject.identifier)
        if testcase and cache_key in self.cache:
            return [res for res in self.cache[cache_key] if res['testcase']['name'] == testcase]

        # Try to get passing test case result from external cache.
        external_cache_key = None
        if testcase:
            external_cache_key = (
                "greenwave.resources:ResultsRetriever|"
                f"{subject.type} {subject.identifier} {testcase}")
            results = self.get_external_cache(external_cache_key)
            if results and self._results_match_time(results):
                return results

        params = {
            '_distinct_on': 'scenario,system_architecture,system_variant'
        }
        if self.since:
            params.update({'since': self.since})
        if testcase:
            params.update({'testcases': testcase})

        results = []
        for query in subject.result_queries():
            query.update(params)
            results.extend(self._retrieve_data(query))

        if not testcase:
            self.cache[cache_key] = results

        # Store test case results in external cache if all are passing,
        # otherwise retrieve from ResultsDB again later.
        if external_cache_key and all(
                result.get('outcome') in current_app.config['OUTCOMES_PASSED']
                for result in results):
            self.set_external_cache(external_cache_key, results)

        return results

    def _make_request(self, params, **request_args):
        return requests_session.get(
            self.url + '/results/latest',
            params=params,
            **request_args)

    def _results_match_time(self, results):
        if not self.since:
            return True

        until = self.since.split(',')[1]
        return all(result['submit_time'] < until for result in results)

    def get_external_cache(self, key):
        return current_app.cache.get(key)

    def set_external_cache(self, key, value):
        current_app.cache.set(key, value)


class WaiversRetriever(BaseRetriever):
    """
    Retrieves waivers from WaiverDB.
    """

    def _retrieve_all(self, filters):
        if self.since:
            for filter_ in filters:
                filter_.update({'since': self.since})
        waivers = self._retrieve_data(filters)
        return [waiver for waiver in waivers if waiver['waived']]

    def _make_request(self, params, **request_args):
        return requests_session.post(
            self.url + '/waivers/+filtered',
            json={'filters': params},
            **request_args)


class NoSourceException(RuntimeError):
    pass


@cached
def retrieve_koji_build_target(nvr, koji_url):
    log.debug('Getting Koji task request ID %r', nvr)
    proxy = get_server_proxy(koji_url, _requests_timeout())
    task_request = proxy.getTaskRequest(nvr)
    if isinstance(task_request, list) and len(task_request) > 1:
        target = task_request[1]
        if isinstance(target, str):
            return target
    return None


@cached
def retrieve_koji_task_id_and_source(nvr, koji_url):
    log.debug('Getting Koji build %r', nvr)
    proxy = get_server_proxy(koji_url, _requests_timeout())
    build = proxy.getBuild(nvr)
    if not build:
        raise NotFound(
            'Failed to find Koji build for "{}" at "{}"'.format(nvr, koji_url)
        )

    task_id = build.get("task_id")

    try:
        source = build["extra"]["source"]["original_url"]
    except (TypeError, KeyError, AttributeError):
        source = build.get("source")

    return (task_id, source)


def retrieve_scm_from_koji(nvr):
    """Retrieve cached rev and namespace from koji using the nvr"""
    koji_url = current_app.config["KOJI_BASE_URL"]
    try:
        _, source = retrieve_koji_task_id_and_source(nvr, koji_url)
    except (xmlrpc.client.ProtocolError, socket.error) as err:
        raise ConnectionError("Could not reach Koji: {}".format(err))
    return retrieve_scm_from_koji_build(nvr, source, koji_url)


def retrieve_scm_from_koji_build(nvr, source, koji_url):
    if not source:
        raise NoSourceException(
            'Failed to retrieve SCM URL from Koji build "{}" at "{}" '
            '(expected SCM URL in "source" attribute)'.format(nvr, koji_url)
        )

    url = urlparse(source)

    path_components = url.path.rsplit('/', 2)
    if len(path_components) < 3:
        namespace = ""
    else:
        namespace = path_components[-2]

    rev = url.fragment
    if not rev:
        raise BadGateway(
            'Failed to parse SCM URL "{}" from Koji build "{}" at "{}" '
            '(missing URL fragment with SCM revision information)'.format(source, nvr, koji_url)
        )

    pkg_name = url.path.split('/')[-1]
    pkg_name = re.sub(r'\.git$', '', pkg_name)
    return namespace, pkg_name, rev


@cached
def retrieve_yaml_remote_rule(url):
    """ Retrieve a remote rule file content from the git web UI. """
    response = requests_session.request('HEAD', url)
    if response.status_code == 404:
        log.debug(f'Server returned 404 for {url}.')
        return None

    if response.status_code != 200:
        raise BadGateway('Error occurred while retrieving a remote rule file from the repo.')

    # remote rule file found...
    response = requests_session.request('GET', url)
    response.raise_for_status()
    return response.content
