#!/usr/bin/env python3

import glob
import os
import re

from charmhelpers.core import (
    host,
    hookenv,
)

from charms.reactive import (
    main,
    set_flag,
    clear_flag,
    is_flag_set,
    hook,
    when_all,
    when_not,
    when_not_all,
)

from charms.reactive.helpers import data_changed
from charmhelpers.core.templating import render


def status(status, msg):
    hookenv.log('%s: %s' % (status, msg))
    hookenv.status_set(status, msg)


def active(msg):
    status('active', msg)


def blocked(msg):
    status('blocked', msg)


def maint(msg):
    status('maintenance', msg)


def write_config_file(push_gateway):
    """
    Create /etc/charmbuild-kpi-import.ini.
    """
    cfg_file = 'charmbuild-kpi-import.ini'
    maint('rendering config %s' % (cfg_file,))
    script_dir = '/srv/charmbuild-kpi-import/parts'
    scripts = [x for x in os.listdir(
        script_dir) if re.match(r'^[-_A-Za-z]+$', x)]
    render(
        source=cfg_file,
        target='/etc/' + cfg_file,
        perms=0o755,
        context={
            'push_gateway': push_gateway,
            'scripts': scripts,
            'config': hookenv.config(),
        },
    )
    return push_gateway


def write_cron_job():
    """
    Create cron job
    """
    dst = '/etc/cron.d/charmbuild-kpi-import'
    cron_job = 'cron-job'
    maint('installing %s to %s' % (cron_job, dst))
    render(
        source=cron_job,
        target=dst,
        perms=0o755,
        context={
            'script_dir': '/srv/charmbuild-kpi-import/parts',
            'script_name': 'charmbuild-kpi-import',
            'user': 'ubuntu',
        },
    )


@when_all('charmbuild.installed',
          'config.set.ga-credentials',
          'prometheus.available')
def write_config(prometheus):
    push_gateway = prometheus.private_address()
    ga_creds = hookenv.config('ga-credentials')
    new_data = data_changed('config', [push_gateway, ga_creds])
    upgrade = is_flag_set('charmbuild.upgrade')
    if new_data or upgrade:
        write_config_file(push_gateway)
        write_cron_job()
        clear_flag('charmbuild.upgrade')
    active('Configured push gateway %s' % (push_gateway,))


@when_not_all('config.set.ga-credentials',
              'prometheus.available')
def not_configured():
    if not is_flag_set('config.set.ga-credentials'):
        blocked('ga-credentials must be set')
    else:
        blocked('Waiting for push-gateway relation')


@hook('upgrade-charm')
def upgrade():
    set_flag('charmbuild.upgrade')
    clear_flag('charmbuild.installed')


@when_not('charmbuild.installed')
def install():
    # this part lifted from haproxy charm hooks.py
    src = os.path.join(os.environ["CHARM_DIR"], "scripts")
    dst = '/srv/charmbuild-kpi-import/parts/'
    maint('Copying scripts from %s to %s' % (src, dst))
    host.mkdir(dst, perms=0o755)
    for fname in glob.glob(os.path.join(src, "*")):
        host.rsync(fname, os.path.join(dst, os.path.basename(fname)))
    set_flag('charmbuild.installed')


if __name__ == '__main__':
    main()
