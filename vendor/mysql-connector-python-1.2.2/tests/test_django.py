# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2014, Oracle and/or its affiliates. All rights reserved.

# MySQL Connector/Python is licensed under the terms of the GPLv2
# <http://www.gnu.org/licenses/old-licenses/gpl-2.0.html>, like most
# MySQL Connectors. There are special exceptions to the terms and
# conditions of the GPLv2 as it is applied to this software, see the
# FOSS License Exception
# <http://www.mysql.com/about/legal/licensing/foss-exception.html>.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

"""Unittests for mysql.connector.django
"""

import sys

import tests

# Load 3rd party _after_ loading tests
from django.conf import settings

# Have to setup Django before loading anything else
settings.configure()
DBCONFIG = tests.get_mysql_config()

settings.DATABASES = {
    'default': {
        'ENGINE': 'mysql.connector.django',
        'NAME': DBCONFIG['database'],
        'USER': 'root',
        'PASSWORD': '',
        'HOST': DBCONFIG['host'],
        'PORT': DBCONFIG['port'],
        'TEST_CHARSET': 'utf8',
        'TEST_COLLATION': 'utf8_general_ci',
    },
}
settings.SECRET_KEY = "django_tests_secret_key"
settings.TIME_ZONE = 'UTC'
settings.USE_TZ = False
settings.SOUTH_TESTS_MIGRATE = False
settings.DEBUG = False

TABLES = {}
TABLES['django_t1'] = """
CREATE TABLE {table_name} (
id INT NOT NULL AUTO_INCREMENT,
c1 INT,
c2 VARCHAR(20),
INDEX (c1),
UNIQUE INDEX (c2),
PRIMARY KEY (id)
) ENGINE=InnoDB
"""

TABLES['django_t2'] = """
CREATE TABLE {table_name} (
id INT NOT NULL AUTO_INCREMENT,
id_t1 INT NOT NULL,
INDEX (id_t1),
PRIMARY KEY (id),
FOREIGN KEY (id_t1) REFERENCES django_t1(id) ON DELETE CASCADE
) ENGINE=InnoDB
"""

# Have to load django.db to make importing db backend work for Django < 1.6
import django.db  # pylint: disable=W0611
if tests.DJANGO_VERSION >= (1, 6):
    from django.db.backends import FieldInfo

from mysql.connector.django.base import DatabaseWrapper
from mysql.connector.django.introspection import DatabaseIntrospection


class DjangoIntrospection(tests.MySQLConnectorTests):

    """Test the Django introspection module"""

    cnx = None
    introspect = None

    def setUp(self):
        # Python 2.6 has no setUpClass, we run it here, once.
        if sys.version_info < (2, 7) and not self.__class__.cnx:
            self.__class__.setUpClass()

    @classmethod
    def setUpClass(cls):
        dbconfig = tests.get_mysql_config()
        cls.cnx = DatabaseWrapper(settings.DATABASES['default'])
        cls.introspect = DatabaseIntrospection(cls.cnx)

        cur = cls.cnx.cursor()

        for table_name, sql in TABLES.items():
            cur.execute("SET foreign_key_checks = 0")
            cur.execute("DROP TABLE IF EXISTS {table_name}".format(
                table_name=table_name))
            cur.execute(sql.format(table_name=table_name))
        cur.execute("SET foreign_key_checks = 1")

    @classmethod
    def tearDownClass(cls):
        cur = cls.cnx.cursor()
        cur.execute("SET foreign_key_checks = 0")
        for table_name, sql in TABLES.items():
            cur.execute("DROP TABLE IF EXISTS {table_name}".format(
                table_name=table_name))
        cur.execute("SET foreign_key_checks = 1")

    def test_get_table_list(self):
        cur = self.cnx.cursor()
        exp = list(TABLES.keys())
        for exp in list(TABLES.keys()):
            if sys.version_info < (2, 7):
                self.assertTrue(exp in self.introspect.get_table_list(cur))
            else:
                self.assertIn(exp, self.introspect.get_table_list(cur),
                              "Table {table_name} not in table list".format(
                                  table_name=exp))

    def test_get_table_description(self):
        cur = self.cnx.cursor()

        if tests.DJANGO_VERSION < (1, 6):
            exp = [
                ('id', 3, None, None, None, None, 0, 16899),
                ('c1', 3, None, None, None, None, 1, 16392),
                ('c2', 253, None, 20, None, None, 1, 16388)
            ]
        else:
            exp = [
                FieldInfo(name='id', type_code=3, display_size=None,
                          internal_size=None, precision=None, scale=None,
                          null_ok=0),
                FieldInfo(name='c1', type_code=3, display_size=None,
                          internal_size=None, precision=None, scale=None,
                          null_ok=1),
                FieldInfo(name='c2', type_code=253, display_size=None,
                          internal_size=20, precision=None, scale=None,
                          null_ok=1)
            ]
        res = self.introspect.get_table_description(cur, 'django_t1')
        self.assertEqual(exp, res)

    def test_get_relations(self):
        cur = self.cnx.cursor()
        exp = {1: (0, 'django_t1')}
        self.assertEqual(exp, self.introspect.get_relations(cur, 'django_t2'))

    def test_get_key_columns(self):
        cur = self.cnx.cursor()
        exp = [('id_t1', 'django_t1', 'id')]
        self.assertEqual(exp, self.introspect.get_key_columns(cur, 'django_t2'))

    def test_get_indexes(self):
        cur = self.cnx.cursor()
        exp = {
            'c1': {'primary_key': False, 'unique': False},
            'id': {'primary_key': True, 'unique': True},
            'c2': {'primary_key': False, 'unique': True}
        }
        self.assertEqual(exp, self.introspect.get_indexes(cur, 'django_t1'))

    def test_get_primary_key_column(self):
        cur = self.cnx.cursor()
        res = self.introspect.get_primary_key_column(cur, 'django_t1')
        self.assertEqual('id', res)
