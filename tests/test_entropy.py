# Copyright (C) Dnspython Contributors, see LICENSE for text of ISC license

import unittest

import dns.entropy

# these tests are mostly for minimal coverage testing

class EntropyTestCase(unittest.TestCase):
    def test_pool(self):
        pool = dns.entropy.EntropyPool(b'seed-value')
        self.assertEqual(pool.random_8(), 94)
        self.assertEqual(pool.random_16(), 61532)
        self.assertEqual(pool.random_32(), 4226376065)
        self.assertEqual(pool.random_between(10, 50), 29)

    def test_functions(self):
        v = dns.entropy.random_16()
        self.assertTrue(0 <= v <= 65535)
        v = dns.entropy.between(10, 50)
        self.assertTrue(10 <= v <= 50)
