# SPDX-License-Identifier: GPL-2.0+
import os


def _local_conf_dir(subdir):
    basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(basedir, 'conf', subdir)


class Config(object):
    """
    A GreenWave Flask configuration.
    """
    DEBUG = True
    # We configure logging explicitly, turn off the Flask-supplied log handler.
    LOGGER_HANDLER_POLICY = 'never'
    HOST = '0.0.0.0'
    PORT = 5005
    PRODUCTION = False
    SECRET_KEY = 'replace-me-with-something-random'

    RESULTSDB_API_URL = 'https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0'
    WAIVERDB_API_URL = 'https://waiverdb.fedoraproject.org/api/v1.0'

    # Remote rule configuration
    DIST_GIT_BASE_URL = 'https://src.fedoraproject.org/'
    DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}{pkg_namespace}/{pkg_name}/raw/{rev}/f/gating.yaml'
    KOJI_BASE_URL = 'https://koji.fedoraproject.org/kojihub'
    # Options for outbound HTTP requests made by python-requests
    REQUESTS_TIMEOUT = (6.1, 15)
    REQUESTS_VERIFY = True

    POLICIES_DIR = '/etc/greenwave/policies'
    SUBJECT_TYPES_DIR = _local_conf_dir('subject_types')

    MESSAGING = 'fedmsg'

    # By default, don't cache anything.
    CACHE = {'backend': 'dogpile.cache.null'}
    # Greenwave API url
    GREENWAVE_API_URL = 'https://greenwave.domain.local/api/v1.0'


class ProductionConfig(Config):
    DEBUG = False
    PRODUCTION = True


class DevelopmentConfig(Config):
    #RESULTSDB_API_URL = 'https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0'
    RESULTSDB_API_URL = 'http://localhost:5001/api/v2.0'
    #WAIVERDB_API_URL = 'http://waiverdb-dev.fedorainfracloud.org/api/v1.0'
    WAIVERDB_API_URL = 'http://localhost:5004/api/v1.0'
    GREENWAVE_API_URL = 'http://localhost:5005/api/v1.0'
    POLICIES_DIR = _local_conf_dir('policies')


class TestingConfig(Config):
    RESULTSDB_API_URL = 'http://localhost:5001/api/v2.0'
    WAIVERDB_API_URL = 'http://localhost:5004/api/v1.0'
    GREENWAVE_API_URL = 'http://localhost:5005/api/v1.0'
    KOJI_BASE_URL = 'http://localhost:5006/kojihub'
    POLICIES_DIR = _local_conf_dir('policies')
