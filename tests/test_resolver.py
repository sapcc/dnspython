# Copyright (C) Dnspython Contributors, see LICENSE for text of ISC license

# Copyright (C) 2003-2017 Nominum, Inc.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose with or without fee is hereby granted,
# provided that the above copyright notice and this permission notice
# appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND NOMINUM DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NOMINUM BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from io import StringIO
import select
import sys
import socket
import time
import unittest

import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.resolver

# Some tests require the internet to be available to run, so let's
# skip those if it's not there.
_network_available = True
try:
    socket.gethostbyname('dnspython.org')
except socket.gaierror:
    _network_available = False

resolv_conf = u"""
    /t/t
# comment 1
; comment 2
domain foo
nameserver 10.0.0.1
nameserver 10.0.0.2
"""

resolv_conf_options1 = """
nameserver 10.0.0.1
nameserver 10.0.0.2
options rotate timeout:1 edns0 ndots:2
"""

message_text = """id 1234
opcode QUERY
rcode NOERROR
flags QR AA RD
;QUESTION
example. IN A
;ANSWER
example. 1 IN A 10.0.0.1
;AUTHORITY
;ADDITIONAL
"""

dangling_cname_0_message_text = """id 10000
opcode QUERY
rcode NOERROR
flags QR AA RD RA
;QUESTION
91.11.17.172.in-addr.arpa.none. IN PTR
;ANSWER
;AUTHORITY
;ADDITIONAL
"""

dangling_cname_1_message_text = """id 10001
opcode QUERY
rcode NOERROR
flags QR AA RD RA
;QUESTION
91.11.17.172.in-addr.arpa. IN PTR
;ANSWER
11.17.172.in-addr.arpa. 86400 IN DNAME 11.8-22.17.172.in-addr.arpa.
91.11.17.172.in-addr.arpa. 86400 IN CNAME 91.11.8-22.17.172.in-addr.arpa.
;AUTHORITY
;ADDITIONAL
"""

dangling_cname_2_message_text = """id 10002
opcode QUERY
rcode NOERROR
flags QR AA RD RA
;QUESTION
91.11.17.172.in-addr.arpa.example. IN PTR
;ANSWER
91.11.17.172.in-addr.arpa.example. 86400 IN CNAME 91.11.17.172.in-addr.arpa.base.
91.11.17.172.in-addr.arpa.base. 86400 IN CNAME 91.11.17.172.clients.example.
91.11.17.172.clients.example. 86400 IN CNAME 91-11-17-172.dynamic.example.
;AUTHORITY
;ADDITIONAL
"""


class FakeAnswer(object):
    def __init__(self, expiration):
        self.expiration = expiration


class BaseResolverTests(unittest.TestCase):

    if sys.platform != 'win32':
        def testRead(self):
            f = StringIO(resolv_conf)
            r = dns.resolver.Resolver(f)
            self.assertEqual(r.nameservers, ['10.0.0.1', '10.0.0.2'])
            self.assertEqual(r.domain, dns.name.from_text('foo'))

        def testReadOptions(self):
            f = StringIO(resolv_conf_options1)
            r = dns.resolver.Resolver(f)
            self.assertEqual(r.nameservers, ['10.0.0.1', '10.0.0.2'])
            self.assertTrue(r.rotate)
            self.assertEqual(r.timeout, 1)
            self.assertEqual(r.ndots, 2)
            self.assertEqual(r.edns, 0)

    def testCacheExpiration(self):
        message = dns.message.from_text(message_text)
        name = dns.name.from_text('example.')
        answer = dns.resolver.Answer(name, dns.rdatatype.A, dns.rdataclass.IN,
                                     message)
        cache = dns.resolver.Cache()
        cache.put((name, dns.rdatatype.A, dns.rdataclass.IN), answer)
        time.sleep(2)
        self.assertTrue(cache.get((name, dns.rdatatype.A, dns.rdataclass.IN))
                        is None)

    def testCacheCleaning(self):
        message = dns.message.from_text(message_text)
        name = dns.name.from_text('example.')
        answer = dns.resolver.Answer(name, dns.rdatatype.A, dns.rdataclass.IN,
                                     message)
        cache = dns.resolver.Cache(cleaning_interval=1.0)
        cache.put((name, dns.rdatatype.A, dns.rdataclass.IN), answer)
        time.sleep(2)
        self.assertTrue(cache.get((name, dns.rdatatype.A, dns.rdataclass.IN))
                        is None)

    def testIndexErrorOnEmptyRRsetAccess(self):
        def bad():
            message = dns.message.from_text(message_text)
            name = dns.name.from_text('example.')
            answer = dns.resolver.Answer(name, dns.rdatatype.MX,
                                         dns.rdataclass.IN, message,
                                         False)
            return answer[0]
        self.assertRaises(IndexError, bad)

    def testIndexErrorOnEmptyRRsetDelete(self):
        def bad():
            message = dns.message.from_text(message_text)
            name = dns.name.from_text('example.')
            answer = dns.resolver.Answer(name, dns.rdatatype.MX,
                                         dns.rdataclass.IN, message,
                                         False)
            del answer[0]
        self.assertRaises(IndexError, bad)

    @unittest.skipIf(not _network_available, "Internet not reachable")
    def testZoneForName1(self):
        name = dns.name.from_text('www.dnspython.org.')
        ezname = dns.name.from_text('dnspython.org.')
        zname = dns.resolver.zone_for_name(name)
        self.assertEqual(zname, ezname)

    @unittest.skipIf(not _network_available, "Internet not reachable")
    def testZoneForName2(self):
        name = dns.name.from_text('a.b.www.dnspython.org.')
        ezname = dns.name.from_text('dnspython.org.')
        zname = dns.resolver.zone_for_name(name)
        self.assertEqual(zname, ezname)

    @unittest.skipIf(not _network_available, "Internet not reachable")
    def testZoneForName3(self):
        name = dns.name.from_text('dnspython.org.')
        ezname = dns.name.from_text('dnspython.org.')
        zname = dns.resolver.zone_for_name(name)
        self.assertEqual(zname, ezname)

    def testZoneForName4(self):
        def bad():
            name = dns.name.from_text('dnspython.org', None)
            dns.resolver.zone_for_name(name)
        self.assertRaises(dns.resolver.NotAbsolute, bad)

    @unittest.skipIf(not _network_available, "Internet not reachable")
    def testResolve(self):
        answer = dns.resolver.resolve('dns.google.', 'A')
        seen = set([rdata.address for rdata in answer])
        self.assertTrue('8.8.8.8' in seen)
        self.assertTrue('8.8.4.4' in seen)

    @unittest.skipIf(not _network_available, "Internet not reachable")
    def testResolveAddress(self):
        answer = dns.resolver.resolve_address('8.8.8.8')
        dnsgoogle = dns.name.from_text('dns.google.')
        self.assertEqual(answer[0].target, dnsgoogle)

    def testLRUReplace(self):
        cache = dns.resolver.LRUCache(4)
        for i in range(0, 5):
            name = dns.name.from_text('example%d.' % i)
            answer = FakeAnswer(time.time() + 1)
            cache.put((name, dns.rdatatype.A, dns.rdataclass.IN), answer)
        for i in range(0, 5):
            name = dns.name.from_text('example%d.' % i)
            if i == 0:
                self.assertTrue(cache.get((name, dns.rdatatype.A,
                                           dns.rdataclass.IN))
                                is None)
            else:
                self.assertTrue(not cache.get((name, dns.rdatatype.A,
                                               dns.rdataclass.IN))
                                is None)

    def testLRUDoesLRU(self):
        cache = dns.resolver.LRUCache(4)
        for i in range(0, 4):
            name = dns.name.from_text('example%d.' % i)
            answer = FakeAnswer(time.time() + 1)
            cache.put((name, dns.rdatatype.A, dns.rdataclass.IN), answer)
        name = dns.name.from_text('example0.')
        cache.get((name, dns.rdatatype.A, dns.rdataclass.IN))
        # The LRU is now example1.
        name = dns.name.from_text('example4.')
        answer = FakeAnswer(time.time() + 1)
        cache.put((name, dns.rdatatype.A, dns.rdataclass.IN), answer)
        for i in range(0, 5):
            name = dns.name.from_text('example%d.' % i)
            if i == 1:
                self.assertTrue(cache.get((name, dns.rdatatype.A,
                                           dns.rdataclass.IN))
                                is None)
            else:
                self.assertTrue(not cache.get((name, dns.rdatatype.A,
                                               dns.rdataclass.IN))
                                is None)

    def testLRUExpiration(self):
        cache = dns.resolver.LRUCache(4)
        for i in range(0, 4):
            name = dns.name.from_text('example%d.' % i)
            answer = FakeAnswer(time.time() + 1)
            cache.put((name, dns.rdatatype.A, dns.rdataclass.IN), answer)
        time.sleep(2)
        for i in range(0, 4):
            name = dns.name.from_text('example%d.' % i)
            self.assertTrue(cache.get((name, dns.rdatatype.A,
                                       dns.rdataclass.IN))
                            is None)

    def testEmptyAnswerSection(self):
        # TODO: dangling_cname_0_message_text was the only sample message
        #       with an empty answer section. Other than that it doesn't
        #       apply.
        message = dns.message.from_text(dangling_cname_0_message_text)
        name = dns.name.from_text('example.')
        answer = dns.resolver.Answer(name, dns.rdatatype.A, dns.rdataclass.IN,
                                     message)
        def test_python_internal_truth(answer):
            if answer:
                return True
            else:
                return False
        self.assertFalse(test_python_internal_truth(answer))
        for a in answer:
            pass

    def testSearchListsRelative(self):
        res = dns.resolver.Resolver()
        res.domain = dns.name.from_text('example')
        res.search = [dns.name.from_text(x) for x in
                      ['dnspython.org', 'dnspython.net']]
        qname = dns.name.from_text('www', None)
        qnames = res._get_qnames_to_try(qname, True)
        self.assertEqual(qnames,
                         [dns.name.from_text(x) for x in
                          ['www.dnspython.org', 'www.dnspython.net']])
        qnames = res._get_qnames_to_try(qname, False)
        self.assertEqual(qnames,
                         [dns.name.from_text('www.example.')])
        qnames = res._get_qnames_to_try(qname, None)
        self.assertEqual(qnames,
                         [dns.name.from_text('www.example.')])
        #
        # Now change search default on resolver to True
        #
        res.use_search_by_default = True
        qnames = res._get_qnames_to_try(qname, None)
        self.assertEqual(qnames,
                         [dns.name.from_text(x) for x in
                          ['www.dnspython.org', 'www.dnspython.net']])

    def testSearchListsAbsolute(self):
        res = dns.resolver.Resolver()
        qname = dns.name.from_text('absolute')
        qnames = res._get_qnames_to_try(qname, True)
        self.assertEqual(qnames, [qname])
        qnames = res._get_qnames_to_try(qname, False)
        self.assertEqual(qnames, [qname])
        qnames = res._get_qnames_to_try(qname, None)
        self.assertEqual(qnames, [qname])

class PollingMonkeyPatchMixin(object):
    def setUp(self):
        self.__native_polling_backend = dns.query._polling_backend
        dns.query._set_polling_backend(self.polling_backend())

        unittest.TestCase.setUp(self)

    def tearDown(self):
        dns.query._set_polling_backend(self.__native_polling_backend)

        unittest.TestCase.tearDown(self)

class SelectResolverTestCase(PollingMonkeyPatchMixin, BaseResolverTests, unittest.TestCase):
    def polling_backend(self):
        return dns.query._select_for

if hasattr(select, 'poll'):
    class PollResolverTestCase(PollingMonkeyPatchMixin, BaseResolverTests, unittest.TestCase):
        def polling_backend(self):
            return dns.query._poll_for


class NXDOMAINExceptionTestCase(unittest.TestCase):

    # pylint: disable=broad-except

    def test_nxdomain_compatible(self):
        n1 = dns.name.Name(('a', 'b', ''))
        n2 = dns.name.Name(('a', 'b', 's', ''))

        try:
            raise dns.resolver.NXDOMAIN
        except dns.exception.DNSException as e:
            self.assertEqual(e.args, (e.__doc__,))
            self.assertTrue(('kwargs' in dir(e)))
            self.assertEqual(str(e), e.__doc__, str(e))
            self.assertTrue(('qnames' not in e.kwargs))
            self.assertTrue(('responses' not in e.kwargs))

        try:
            raise dns.resolver.NXDOMAIN("errmsg")
        except dns.exception.DNSException as e:
            self.assertEqual(e.args, ("errmsg",))
            self.assertTrue(('kwargs' in dir(e)))
            self.assertEqual(str(e), "errmsg", str(e))
            self.assertTrue(('qnames' not in e.kwargs))
            self.assertTrue(('responses' not in e.kwargs))

        try:
            raise dns.resolver.NXDOMAIN("errmsg", -1)
        except dns.exception.DNSException as e:
            self.assertEqual(e.args, ("errmsg", -1))
            self.assertTrue(('kwargs' in dir(e)))
            self.assertEqual(str(e), "('errmsg', -1)", str(e))
            self.assertTrue(('qnames' not in e.kwargs))
            self.assertTrue(('responses' not in e.kwargs))

        try:
            raise dns.resolver.NXDOMAIN(qnames=None)
        except Exception as e:
            self.assertTrue((isinstance(e, AttributeError)))

        try:
            raise dns.resolver.NXDOMAIN(qnames=n1)
        except Exception as e:
            self.assertTrue((isinstance(e, AttributeError)))

        try:
            raise dns.resolver.NXDOMAIN(qnames=[])
        except Exception as e:
            self.assertTrue((isinstance(e, AttributeError)))

        try:
            raise dns.resolver.NXDOMAIN(qnames=[n1])
        except dns.exception.DNSException as e:
            MSG = "The DNS query name does not exist: a.b."
            self.assertEqual(e.args, (MSG,), repr(e.args))
            self.assertTrue(('kwargs' in dir(e)))
            self.assertEqual(str(e), MSG, str(e))
            self.assertTrue(('qnames' in e.kwargs))
            self.assertEqual(e.kwargs['qnames'], [n1])
            self.assertTrue(('responses' in e.kwargs))
            self.assertEqual(e.kwargs['responses'], {})

        try:
            raise dns.resolver.NXDOMAIN(qnames=[n2, n1])
        except dns.resolver.NXDOMAIN as e:
            e0 = dns.resolver.NXDOMAIN("errmsg")
            e = e0 + e
            MSG = "None of DNS query names exist: a.b.s., a.b."
            self.assertEqual(e.args, (MSG,), repr(e.args))
            self.assertTrue(('kwargs' in dir(e)))
            self.assertEqual(str(e), MSG, str(e))
            self.assertTrue(('qnames' in e.kwargs))
            self.assertEqual(e.kwargs['qnames'], [n2, n1])
            self.assertTrue(('responses' in e.kwargs))
            self.assertEqual(e.kwargs['responses'], {})

        try:
            raise dns.resolver.NXDOMAIN(qnames=[n1], responses=['r1.1'])
        except Exception as e:
            self.assertTrue((isinstance(e, AttributeError)))

        try:
            raise dns.resolver.NXDOMAIN(qnames=[n1], responses={n1: 'r1.1'})
        except dns.resolver.NXDOMAIN as e:
            MSG = "The DNS query name does not exist: a.b."
            self.assertEqual(e.args, (MSG,), repr(e.args))
            self.assertTrue(('kwargs' in dir(e)))
            self.assertEqual(str(e), MSG, str(e))
            self.assertTrue(('qnames' in e.kwargs))
            self.assertEqual(e.kwargs['qnames'], [n1])
            self.assertTrue(('responses' in e.kwargs))
            self.assertEqual(e.kwargs['responses'], {n1: 'r1.1'})

    def test_nxdomain_merge(self):
        n1 = dns.name.Name(('a', 'b', ''))
        n2 = dns.name.Name(('a', 'b', ''))
        n3 = dns.name.Name(('a', 'b', 'c', ''))
        n4 = dns.name.Name(('a', 'b', 'd', ''))
        responses1 = {n1: 'r1.1', n2: 'r1.2', n4: 'r1.4'}
        qnames1 = [n1, n4]   # n2 == n1
        responses2 = {n2: 'r2.2', n3: 'r2.3'}
        qnames2 = [n2, n3]
        e0 = dns.resolver.NXDOMAIN()
        e1 = dns.resolver.NXDOMAIN(qnames=qnames1, responses=responses1)
        e2 = dns.resolver.NXDOMAIN(qnames=qnames2, responses=responses2)
        e = e1 + e0 + e2
        self.assertRaises(AttributeError, lambda: e0 + e0)
        self.assertEqual(e.kwargs['qnames'], [n1, n4, n3],
                         repr(e.kwargs['qnames']))
        self.assertTrue(e.kwargs['responses'][n1].startswith('r2.'))
        self.assertTrue(e.kwargs['responses'][n2].startswith('r2.'))
        self.assertTrue(e.kwargs['responses'][n3].startswith('r2.'))
        self.assertTrue(e.kwargs['responses'][n4].startswith('r1.'))

    def test_nxdomain_canonical_name(self):
        cname1 = "91.11.8-22.17.172.in-addr.arpa."
        cname2 = "91-11-17-172.dynamic.example."
        message0 = dns.message.from_text(dangling_cname_0_message_text)
        message1 = dns.message.from_text(dangling_cname_1_message_text)
        message2 = dns.message.from_text(dangling_cname_2_message_text)
        qname0 = message0.question[0].name
        qname1 = message1.question[0].name
        qname2 = message2.question[0].name
        responses = {qname0: message0, qname1: message1, qname2: message2}
        eX = dns.resolver.NXDOMAIN()
        e0 = dns.resolver.NXDOMAIN(qnames=[qname0], responses=responses)
        e1 = dns.resolver.NXDOMAIN(qnames=[qname0, qname1, qname2], responses=responses)
        e2 = dns.resolver.NXDOMAIN(qnames=[qname0, qname2, qname1], responses=responses)
        self.assertRaises(TypeError, lambda: eX.canonical_name)
        self.assertEqual(e0.canonical_name, qname0)
        self.assertEqual(e1.canonical_name, dns.name.from_text(cname1))
        self.assertEqual(e2.canonical_name, dns.name.from_text(cname2))


class ResolverNameserverValidTypeTestCase(unittest.TestCase):
    def test_set_nameservers_to_list(self):
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['1.2.3.4']
        self.assertEqual(resolver.nameservers, ['1.2.3.4'])

    def test_set_namservers_to_empty_list(self):
        resolver = dns.resolver.Resolver()
        resolver.nameservers = []
        self.assertEqual(resolver.nameservers, [])

    def test_set_nameservers_invalid_type(self):
        resolver = dns.resolver.Resolver()
        invalid_nameservers = [None, '1.2.3.4', 1234, (1, 2, 3, 4), {'invalid': 'nameserver'}]
        for invalid_nameserver in invalid_nameservers:
            with self.assertRaises(ValueError):
                resolver.nameservers = invalid_nameserver

if __name__ == '__main__':
    unittest.main()
