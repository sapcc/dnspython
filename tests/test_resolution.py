import unittest

import dns.message
import dns.name
import dns.rcode
import dns.rdataclass
import dns.rdatatype
import dns.resolver

# Test the resolver's Resolution, i.e. the business logic of the resolver.

class ResolutionTestCase(unittest.TestCase):
    def setUp(self):
        self.resolver = dns.resolver.Resolver(configure=False)
        self.resolver.nameservers = ['10.0.0.1', '10.0.0.2']
        self.resolver.domain = dns.name.from_text('example')
        self.qname = dns.name.from_text('www.dnspython.org')
        self.resn = dns.resolver._Resolution(self.resolver, self.qname,
                                             'A', 'IN',
                                             False, True, False)

    def test_next_request_abs(self):
        (request, answer) = self.resn.next_request()
        self.assertTrue(answer is None)
        self.assertEqual(request.question[0].name, self.qname)
        self.assertEqual(request.question[0].rdtype, dns.rdatatype.A)

    def test_next_request_rel(self):
        qname = dns.name.from_text('www.dnspython.org', None)
        abs_qname_1 = dns.name.from_text('www.dnspython.org.example')
        self.resn = dns.resolver._Resolution(self.resolver, qname,
                                             'A', 'IN',
                                             False, True, False)
        (request, answer) = self.resn.next_request()
        self.assertTrue(answer is None)
        self.assertEqual(request.question[0].name, self.qname)
        self.assertEqual(request.question[0].rdtype, dns.rdatatype.A)
        (request, answer) = self.resn.next_request()
        self.assertTrue(answer is None)
        self.assertEqual(request.question[0].name, abs_qname_1)
        self.assertEqual(request.question[0].rdtype, dns.rdatatype.A)

    def test_next_request_exhaust_causes_nxdomain(self):
        def bad():
            (request, answer) = self.resn.next_request()
        (request, answer) = self.resn.next_request()
        self.assertRaises(dns.resolver.NXDOMAIN, bad)

    def make_address_response(self, q):
        r = dns.message.make_response(q)
        rrs = r.get_rrset(r.answer, self.qname, dns.rdataclass.IN,
                          dns.rdatatype.A, create=True)
        rrs.add(dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A,
                                    '10.0.0.1'), 300)
        return r

    def make_negative_response(self, q, nxdomain=False):
        r = dns.message.make_response(q)
        rrs = r.get_rrset(r.authority, q.question[0].name, dns.rdataclass.IN,
                          dns.rdatatype.SOA, create=True)
        rrs.add(dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.SOA,
                                    '. . 1 2 3 4 300'), 300)
        if nxdomain:
            r.set_rcode(dns.rcode.NXDOMAIN)
        return r

    def test_next_request_cache_hit(self):
        self.resolver.cache = dns.resolver.Cache()
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        cache_answer = dns.resolver.Answer(self.qname, dns.rdatatype.A,
                                           dns.rdataclass.IN, r)
        self.resolver.cache.put((self.qname, dns.rdatatype.A,
                                 dns.rdataclass.IN), cache_answer)
        (request, answer) = self.resn.next_request()
        self.assertTrue(request is None)
        self.assertTrue(answer is cache_answer)

    def test_next_request_cached_no_answer(self):
        # In default mode, we should raise on a no-answer hit
        self.resolver.cache = dns.resolver.Cache()
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        # Note we need an SOA so the cache doesn't expire the answer
        # immediately, but our negative response code does that.
        r = self.make_negative_response(q)
        cache_answer = dns.resolver.Answer(self.qname, dns.rdatatype.A,
                                           dns.rdataclass.IN, r)
        self.resolver.cache.put((self.qname, dns.rdatatype.A,
                                 dns.rdataclass.IN), cache_answer)
        def bad():
            (request, answer) = self.resn.next_request()
        self.assertRaises(dns.resolver.NoAnswer, bad)
        # If raise_on_no_answer is False, we should get a cache hit.
        self.resn = dns.resolver._Resolution(self.resolver, self.qname,
                                             'A', 'IN',
                                             False, False, False)
        (request, answer) = self.resn.next_request()
        self.assertTrue(request is None)
        self.assertTrue(answer is cache_answer)

    def test_next_request_cached_nxdomain(self):
        # use a relative qname so we have two qnames to try
        qname = dns.name.from_text('www.dnspython.org', None)
        self.resn = dns.resolver._Resolution(self.resolver, qname,
                                             'A', 'IN',
                                             False, True, False)
        qname1 = dns.name.from_text('www.dnspython.org.example.')
        qname2 = dns.name.from_text('www.dnspython.org.')
        # Arrange to get NXDOMAIN hits on both of those qnames.
        self.resolver.cache = dns.resolver.Cache()
        q1 = dns.message.make_query(qname1, dns.rdatatype.A)
        r1 = self.make_negative_response(q1, True)
        cache_answer = dns.resolver.Answer(qname1, dns.rdatatype.ANY,
                                           dns.rdataclass.IN, r1)
        self.resolver.cache.put((qname1, dns.rdatatype.ANY,
                                 dns.rdataclass.IN), cache_answer)
        q2 = dns.message.make_query(qname2, dns.rdatatype.A)
        r2 = self.make_negative_response(q2, True)
        cache_answer = dns.resolver.Answer(qname2, dns.rdatatype.ANY,
                                           dns.rdataclass.IN, r2)
        self.resolver.cache.put((qname2, dns.rdatatype.ANY,
                                 dns.rdataclass.IN), cache_answer)
        try:
            (request, answer) = self.resn.next_request()
            self.assertTrue(False)  # should not happen!
        except dns.resolver.NXDOMAIN as nx:
            self.assertTrue(nx.response(qname1) is r1)
            self.assertTrue(nx.response(qname2) is r2)

    def test_next_nameserver_udp(self):
        (request, answer) = self.resn.next_request()
        (nameserver1, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver1 in self.resolver.nameservers)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.0)
        (nameserver2, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver2 in self.resolver.nameservers)
        self.assertTrue(nameserver2 != nameserver1)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.0)
        (nameserver3, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver3 is nameserver1)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.1)
        (nameserver4, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver4 is nameserver2)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.0)
        (nameserver5, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver5 is nameserver1)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.2)

    def test_next_nameserver_retry_with_tcp(self):
        (request, answer) = self.resn.next_request()
        (nameserver1, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver1 in self.resolver.nameservers)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.0)
        self.resn.retry_with_tcp = True
        (nameserver2, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver2 is nameserver1)
        self.assertEqual(port, 53)
        self.assertTrue(tcp)
        self.assertEqual(backoff, 0.0)
        (nameserver3, port, tcp, backoff) = self.resn.next_nameserver()
        self.assertTrue(nameserver3 in self.resolver.nameservers)
        self.assertTrue(nameserver3 != nameserver1)
        self.assertEqual(port, 53)
        self.assertFalse(tcp)
        self.assertEqual(backoff, 0.0)

    def test_next_nameserver_no_nameservers(self):
        (request, answer) = self.resn.next_request()
        (nameserver, _, _, _) = self.resn.next_nameserver()
        self.resn.nameservers.remove(nameserver)
        (nameserver, _, _, _) = self.resn.next_nameserver()
        self.resn.nameservers.remove(nameserver)
        def bad():
            (nameserver, _, _, _) = self.resn.next_nameserver()
        self.assertRaises(dns.resolver.NoNameservers, bad)

    def test_query_result_nameserver_removing_exceptions(self):
        # add some nameservers so we have enough to remove :)
        self.resolver.nameservers.extend(['10.0.0.3', '10.0.0.4'])
        (request, _) = self.resn.next_request()
        exceptions = [dns.exception.FormError(), EOFError(),
                      NotImplementedError(), dns.message.Truncated()]
        for i in range(4):
            (nameserver, _, _, _) = self.resn.next_nameserver()
            if i == 3:
                # Truncated is only bad if we're doing TCP, make it look
                # like that's the case
                self.resn.tcp_attempt = True
            self.assertTrue(nameserver in self.resn.nameservers)
            (answer, done) = self.resn.query_result(None, exceptions[i])
            self.assertTrue(answer is None)
            self.assertFalse(done)
            self.assertFalse(nameserver in self.resn.nameservers)
        self.assertEqual(len(self.resn.nameservers), 0)

    def test_query_result_nameserver_continuing_exception(self):
        # except for the exceptions tested in
        # test_query_result_nameserver_removing_exceptions(), we should
        # not remove any nameservers and just continue resolving.
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        nameservers = self.resn.nameservers[:]
        (answer, done) = self.resn.query_result(None, dns.exception.Timeout())
        self.assertTrue(answer is None)
        self.assertFalse(done)
        self.assertEqual(nameservers, self.resn.nameservers)

    def test_query_result_retry_with_tcp(self):
        (request, _) = self.resn.next_request()
        (nameserver, _, tcp, _) = self.resn.next_nameserver()
        self.assertFalse(tcp)
        (answer, done) = self.resn.query_result(None, dns.message.Truncated())
        self.assertTrue(answer is None)
        self.assertFalse(done)
        self.assertTrue(self.resn.retry_with_tcp)
        # The rest of TCP retry logic was tested above in
        # test_next_nameserver_retry_with_tcp(), so we do not repeat
        # it.

    def test_query_result_no_error_with_data(self):
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        (answer, done) = self.resn.query_result(r, None)
        self.assertFalse(answer is None)
        self.assertTrue(done)
        self.assertEqual(answer.qname, self.qname)
        self.assertEqual(answer.rdtype, dns.rdatatype.A)

    def test_query_result_no_error_with_data_cached(self):
        self.resolver.cache = dns.resolver.Cache()
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        (answer, done) = self.resn.query_result(r, None)
        self.assertFalse(answer is None)
        cache_answer = self.resolver.cache.get((self.qname, dns.rdatatype.A,
                                                dns.rdataclass.IN))
        self.assertTrue(answer is cache_answer)

    def test_query_result_no_error_no_data(self):
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_negative_response(q)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        def bad():
            (answer, done) = self.resn.query_result(r, None)
        self.assertRaises(dns.resolver.NoAnswer, bad)

    def test_query_result_nxdomain(self):
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_negative_response(q, True)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        (answer, done) = self.resn.query_result(r, None)
        self.assertTrue(answer is None)
        self.assertTrue(done)

    def test_query_result_nxdomain_cached(self):
        self.resolver.cache = dns.resolver.Cache()
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_negative_response(q, True)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        (answer, done) = self.resn.query_result(r, None)
        self.assertTrue(answer is None)
        self.assertTrue(done)
        cache_answer = self.resolver.cache.get((self.qname, dns.rdatatype.ANY,
                                                dns.rdataclass.IN))
        self.assertTrue(cache_answer.response is r)

    def test_query_result_yxdomain(self):
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        r.set_rcode(dns.rcode.YXDOMAIN)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        def bad():
            (answer, done) = self.resn.query_result(r, None)
        self.assertRaises(dns.resolver.YXDOMAIN, bad)

    def test_query_result_servfail_no_retry(self):
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        r.set_rcode(dns.rcode.SERVFAIL)
        (_, _) = self.resn.next_request()
        (nameserver, _, _, _) = self.resn.next_nameserver()
        (answer, done) = self.resn.query_result(r, None)
        self.assertTrue(answer is None)
        self.assertFalse(done)
        self.assertTrue(nameserver not in self.resn.nameservers)

    def test_query_result_servfail_with_retry(self):
        self.resolver.retry_servfail = True
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        r.set_rcode(dns.rcode.SERVFAIL)
        (_, _) = self.resn.next_request()
        (_, _, _, _) = self.resn.next_nameserver()
        nameservers = self.resn.nameservers[:]
        (answer, done) = self.resn.query_result(r, None)
        self.assertTrue(answer is None)
        self.assertFalse(done)
        self.assertEqual(nameservers, self.resn.nameservers)

    def test_query_result_other_unhappy_rcode(self):
        q = dns.message.make_query(self.qname, dns.rdatatype.A)
        r = self.make_address_response(q)
        r.set_rcode(dns.rcode.REFUSED)
        (_, _) = self.resn.next_request()
        (nameserver, _, _, _) = self.resn.next_nameserver()
        (answer, done) = self.resn.query_result(r, None)
        self.assertTrue(answer is None)
        self.assertFalse(done)
        self.assertTrue(nameserver not in self.resn.nameservers)
