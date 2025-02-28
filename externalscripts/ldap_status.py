#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__auther__ = 'tsuno teppei'

'''
status code:
0: Processing Complete
400: Failed Load Config
500: Failed Connect LDAP
501: Failed Processing
502: return Not Success
'''
from os import path
from ldap3 import Server, Connection, ALL, ALL_OPERATIONAL_ATTRIBUTES, ALL_ATTRIBUTES
import time
import json
import argparse
import re

# 定数
LDAP_PORT = 389
LDAPS_PORT = 636
CONFIG_DIR = '/var/lib/zabbix/conf.d/'
DEFAULT_CONFIG = 'ldap_status.json'
TIMEOUT = 3

# 変数初期化
result = {
    'status': 0,
    'metrics': {}
}
config = {
    'endpoint': 'localhost',
    'type': 'openldap',
    'secure': 'YES',
    'port': None,
    'user': 'cn=Anonymous,dc=example,dc=com',
    'password': 'password',
    'base': 'dn=monitor',
    'search': '(objectClass=*)',
}

# 引数処理
parser = argparse.ArgumentParser()
parser.add_argument('endpoint', type=str)
parser.add_argument('--config-file', '-c', type=str)
parser.add_argument('--type', '-t', choices=['openldap', '389ds'])
parser.add_argument('--secure', '-s', choices=['YES', 'NO'])
parser.add_argument('--port', '-p',type=int)
parser.add_argument('--user', type=str)
parser.add_argument('--password', type=str)
parser.add_argument('--base', type=str)
parser.add_argument('--search', type=str)
params = parser.parse_args()

if not params.config_file:
    # 設定ファイルの指定がない場合はデフォルトを読み込む
    configFile = path.join(CONFIG_DIR, DEFAULT_CONFIG)
else:
    # 相対パスで上位ディレクトリに移動禁止、拡張子は削除
    params.config_file = params.config_file.replace('../', '').replace('.json', '')
    configFile = path.join(CONFIG_DIR, params.config_file + '.json')

# 設定ファイル読み込み
try:
    with open(configFile, 'r') as file:
        rFile = json.load(file)
        for _key in config.keys():
            if rFile.get(_key):
                config.update(
                    {
                        _key: rFile[_key]
                    }
                )
            # 引数で指定された値があれば上書き
            if params.__getattribute__(_key):
                config.update(
                    {
                        _key: params.__getattribute__(_key)
                    }
                )
except Exception as error:
    # 設定ファイル読み込み失敗
    result.update(
        {
            'status': 400,
            'metrics': {
                'error': str(error)
            }
        }
    )
    print(json.dumps(result))
    exit()

# 変換補完
config['secure'] = True if config['secure'] == "YES" else False
config['port'] = config['port'] if config['port'] else (LDAPS_PORT if config['secure'] else LDAP_PORT)

try:
    # LDAPサーバーへの接続
    server = Server(
        host=config['endpoint'],
        port=config['port'],
        use_ssl=config['secure'],
        get_info=ALL
    )
    conn = Connection(
        server,
        user=config['user'],
        password=config.pop('password'),
        receive_timeout=TIMEOUT
    )
    conn.bind()
except Exception as error:
    # LDAPサーバーへの接続失敗
    result.update(
        {
            'status': 500,
            'metrics': {
                'config': config,
                'error': str(error)
            }
        }
    )
    print(json.dumps(result))
    exit()

# 処理実行
try:
    # 389dsの場合はALL_ATTRIBUTESを指定
    attributes=ALL_ATTRIBUTES if config['type'] == '389ds' else ALL_OPERATIONAL_ATTRIBUTES
    start = time.time()
    if conn.search(config['base'], config['search'], attributes=attributes):
        result['response'] = time.time() - start 
        if conn.result['description'] == 'success':
            # 実行成功
            [result['metrics'].update({res['dn']: dict(res['attributes'])}) for res in conn.response if not re.match('cn=Connection [0-9]*', res['dn'])]
        else:
            # 実行失敗
            result.update(
                {
                    'status': 502,
                    'metrics': {
                        'config': config,
                        'error': 'result description, not success.'
                    }
                }
            )
    else:
        # 実行失敗
        result.update(
            {
                'status': 502,
                'metrics': {
                    'config': config,
                    'error': 'execute search, False.'
                }
            }
        )
except Exception as error:
    # 実行失敗
    result.update(
        {
            'status': 501,
            'metrics': {
                'config': config,
                'error': str(error)
            }
        }
    )

# 結果出力
print(json.dumps(result, default=str))
exit()
# EOS