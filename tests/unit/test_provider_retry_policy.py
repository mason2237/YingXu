import unittest
from yingxu.domain.provider_policy import classify,retry_delay


class RetryPolicyTests(unittest.TestCase):
    def test_categories_and_bound(self):
        self.assertEqual(classify(429),'rate_limited');self.assertEqual(classify(503),'transient')
        self.assertEqual(classify(403),'auth')
        for kind in ('auth','manual','unsupported','security','permanent'):
            self.assertIsNone(retry_delay(kind,0,100))
        self.assertEqual([retry_delay('transient',n,100) for n in range(4)],[2,4,8,None])
        self.assertEqual(retry_delay('rate_limited',0,100,'30'),30)
        self.assertIsNone(retry_delay('rate_limited',0,100,'999999'))
        self.assertIsNone(retry_delay('transient',0,100,'nan'))
