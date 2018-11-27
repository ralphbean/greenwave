# SPDX-License-Identifier: GPL-2.0+

import mock

from textwrap import dedent

import greenwave.app_factory
import greenwave.consumers.resultsdb
from greenwave.policies import Policy


def test_announcement_keys_decode_with_list():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    message = {'msg': {'data': {
        'original_spec_nvr': ['glibc-1.0-1.fc27'],
    }}}
    subjects = list(cls.announcement_subjects(message))

    assert subjects == [('koji_build', 'glibc-1.0-1.fc27')]


def test_announcement_subjects_for_brew_build():
    # The 'brew-build' type appears internally within Red Hat. We treat it as an
    # alias of 'koji_build'.
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    message = {'msg': {'data': {
        'type': 'brew-build',
        'item': ['glibc-1.0-3.fc27'],
    }}}
    subjects = list(cls.announcement_subjects(message))

    assert subjects == [('koji_build', 'glibc-1.0-3.fc27')]


def test_announcement_subjects_for_autocloud_compose():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    message = {
        'msg': {
            'task': {
                'item': 'Fedora-AtomicHost-28_Update-20180723.1839.x86_64.qcow2',
                'type': 'compose',
                'name': 'compose.install_no_user'
            },
            'result': {
                'prev_outcome': None,
                'outcome': 'PASSED',
                'id': 23004689,
                'submit_time': '2018-07-23 21:07:38 UTC',
                'log_url': 'https://apps.fedoraproject.org/autocloud/jobs/9238/output'
            }
        }
    }
    subjects = list(cls.announcement_subjects(message))

    assert subjects == [('compose', 'Fedora-AtomicHost-28_Update-20180723.1839.x86_64.qcow2')]


@mock.patch('greenwave.resources.ResultsRetriever.retrieve')
@mock.patch('greenwave.resources.retrieve_decision')
@mock.patch('greenwave.resources.retrieve_scm_from_koji')
@mock.patch('greenwave.resources.retrieve_yaml_remote_rule')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_remote_rule_decision_change(
        mock_fedmsg,
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_decision,
        mock_retrieve_results):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    # gating.yaml
    gating_yaml = dedent("""
        --- !Policy
        product_versions: [fedora-rawhide, notexisting_prodversion]
        decision_context: test_context
        rules:
          - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
    """)
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)

    nvr = 'nethack-1.2.3-1.rawhide'
    result = {
        'id': 1,
        'testcase': {'name': 'dist.rpmdeplint'},
        'outcome': 'PASSED',
        'data': {'item': nvr, 'type': 'koji_build'},
    }
    mock_retrieve_results.return_value = [result]

    def retrieve_decision(url, data):
        #pylint: disable=unused-argument
        if 'ignore_result' in data:
            return None
        return {}
    mock_retrieve_decision.side_effect = retrieve_decision
    mock_retrieve_scm_from_koji.return_value = ('rpms', nvr,
                                                'c3c47a08a66451cb9686c49f040776ed35a0d1bb')

    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                }
            }
        }
    }
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

    handler.flask_app.config['policies'] = Policy.safe_load_all(policies)
    with handler.flask_app.app_context():
        handler.consume(message)

    assert len(mock_fedmsg.mock_calls) == 1

    mock_call = mock_fedmsg.mock_calls[0][2]
    assert mock_call['topic'] == 'decision.update'

    actual_msgs_sent = [mock_call['msg'] for call in mock_fedmsg.mock_calls]
    assert actual_msgs_sent[0] == {
        'decision_context': 'test_context',
        'product_version': 'fedora-rawhide',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'previous': None,
    }


@mock.patch('greenwave.resources.ResultsRetriever.retrieve')
@mock.patch('greenwave.resources.retrieve_decision')
@mock.patch('greenwave.resources.retrieve_scm_from_koji')
@mock.patch('greenwave.resources.retrieve_yaml_remote_rule')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_remote_rule_decision_change_not_matching(
        mock_fedmsg,
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_decision,
        mock_retrieve_results):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    # gating.yaml
    gating_yaml = dedent("""
        --- !Policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        rules:
          - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
    """)
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: another_test_context
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)

    nvr = 'nethack-1.2.3-1.rawhide'
    result = {
        'id': 1,
        'testcase': {'name': 'dist.rpmdeplint'},
        'outcome': 'PASSED',
        'data': {'item': nvr, 'type': 'koji_build'},
    }
    mock_retrieve_results.return_value = [result]

    def retrieve_decision(url, data):
        #pylint: disable=unused-argument
        if 'ignore_result' in data:
            return None
        return {}
    mock_retrieve_decision.side_effect = retrieve_decision
    mock_retrieve_scm_from_koji.return_value = ('rpms', nvr,
                                                'c3c47a08a66451cb9686c49f040776ed35a0d1bb')

    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                }
            }
        }
    }
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

    handler.flask_app.config['policies'] = Policy.safe_load_all(policies)
    with handler.flask_app.app_context():
        handler.consume(message)

    assert len(mock_fedmsg.mock_calls) == 0


def test_guess_product_version_failing():
    # pylint: disable=W0212
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)
    with handler.flask_app.app_context():
        product_version = greenwave.consumers.resultsdb._subject_product_version(
            'release-e2e-test-1.0.1685-1.el5', 'koji_build')
        assert product_version == 'rhel-5'

        product_version = greenwave.consumers.resultsdb._subject_product_version(
            'rust-toolset-rhel8-20181010170614.b09eea91', 'redhat-module')
        assert product_version == 'rhel-8'
