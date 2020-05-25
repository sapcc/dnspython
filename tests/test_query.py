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

import socket
import unittest

import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.query

# Some tests require the internet to be available to run, so let's
# skip those if it's not there.
_network_available = True
try:
    socket.gethostbyname('dnspython.org')
except socket.gaierror:
    _network_available = False

@unittest.skipIf(not _network_available, "Internet not reachable")
class QueryTests(unittest.TestCase):

    def testQueryUDP(self):
        qname = dns.name.from_text('dns.google.')
        q = dns.message.make_query(qname, dns.rdatatype.A)
        response = dns.query.udp(q, '8.8.8.8')
        rrs = response.get_rrset(response.answer, qname,
                                 dns.rdataclass.IN, dns.rdatatype.A)
        self.assertTrue(rrs is not None)
        seen = set([rdata.address for rdata in rrs])
        self.assertTrue('8.8.8.8' in seen)
        self.assertTrue('8.8.4.4' in seen)

    def testQueryTCP(self):
        qname = dns.name.from_text('dns.google.')
        q = dns.message.make_query(qname, dns.rdatatype.A)
        response = dns.query.tcp(q, '8.8.8.8')
        rrs = response.get_rrset(response.answer, qname,
                                 dns.rdataclass.IN, dns.rdatatype.A)
        self.assertTrue(rrs is not None)
        seen = set([rdata.address for rdata in rrs])
        self.assertTrue('8.8.8.8' in seen)
        self.assertTrue('8.8.4.4' in seen)

    def testQueryTLS(self):
        qname = dns.name.from_text('dns.google.')
        q = dns.message.make_query(qname, dns.rdatatype.A)
        response = dns.query.tls(q, '8.8.8.8')
        rrs = response.get_rrset(response.answer, qname,
                                 dns.rdataclass.IN, dns.rdatatype.A)
        self.assertTrue(rrs is not None)
        seen = set([rdata.address for rdata in rrs])
        self.assertTrue('8.8.8.8' in seen)
        self.assertTrue('8.8.4.4' in seen)

    def testQueryUDPFallback(self):
        qname = dns.name.from_text('.')
        q = dns.message.make_query(qname, dns.rdatatype.DNSKEY)
        (_, tcp) = dns.query.udp_with_fallback(q, '8.8.8.8')
        self.assertTrue(tcp)

    def testQueryUDPFallbackNoFallback(self):
        qname = dns.name.from_text('dns.google.')
        q = dns.message.make_query(qname, dns.rdatatype.A)
        (_, tcp) = dns.query.udp_with_fallback(q, '8.8.8.8')
        self.assertFalse(tcp)
