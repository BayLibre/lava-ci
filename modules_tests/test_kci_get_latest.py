#!/usr/bin/python
###############################################################################
## @package test_kci_get_latest
# @brief Test the kci_get_latest module
#
import os,sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

import unittest
import kci_get_latest

from lib import configuration

import pdb

class test_kci_get_latest(unittest.TestCase):

    def setUp(self):
        pass
    def tearDown(self):
        pass

    def test_001_get_latest_tags(self):
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':None,'last':None}
        config = configuration.get_config(args)

        res=kci_get_latest.get_latest_tags(config)

        print res
        self.assertIsInstance(res,list)
        self.assertEqual(len(res),1)

    def test_002_get_latest_tags(self):
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':'mainline','last':None}
        config1 = configuration.get_config(args)

        res1=kci_get_latest.get_latest_tags(config1)

        print res1
        self.assertIsInstance(res1,list)
        self.assertEqual(len(res1),1)
        self.assertIn('mainline/',res1[0])

        args['job']='stable'
        config2 = configuration.get_config(args)

        res2=kci_get_latest.get_latest_tags(config2)

        print res2
        self.assertIsInstance(res2,list)
        self.assertEqual(len(res2),1)
        self.assertIn('stable/',res2[0])


    def test_003_get_latest_tags(self):
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':None,'last':'next/next-20160727'}
        config1 = configuration.get_config(args)

        res1=kci_get_latest.get_latest_tags(config1)

        print res1
        self.assertIsInstance(res1,list)
        self.assertGreater(len(res1),1)
        self.assertIn('next/next-20160727',res1[len(res1)-1])

    def test_004_get_latest_tags(self):
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        config1 = configuration.get_config(args)

        res1=kci_get_latest.get_latest_tags(config1)

        print res1
        self.assertIsInstance(res1,list)
        self.assertGreater(len(res1),1)
        for r in res1:
            self.assertIn('mainline/',r)

    def test_005_run(self):
        args={'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        
        with self.assertRaises(ValueError) as context:
            kci_get_latest.run(args)
        self.assertTrue("No token found in config" in context.exception)       
        
        args={'api':"http://api.kernelci.org",'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        
        with self.assertRaises(ValueError) as context:
            kci_get_latest.run(args)
        self.assertTrue("No token found in config" in context.exception)       
        
    def test_006_run(self):
        args={'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        
        with self.assertRaises(ValueError) as context:
            kci_get_latest.run(args)
        self.assertTrue("No api found in config" in context.exception)       
        
    def test_007_kci_get_latest(self):
        res=kci_get_latest.kci_get_latest("http://api.kernelci.org","bb4d438a-f412-4c65-9f7c-9daefd253ee7")
        self.assertIn('mainline/',res[0])
        
    def test_008_kci_get_latest(self):
        res=kci_get_latest.kci_get_latest("http://api.kernelci.org","")
        self.assertEqual(res,1)
        
    def test_009_kci_get_latest(self):
        res=kci_get_latest.kci_get_latest("","bb4d438a-f412-4c65-9f7c-9daefd253ee7")
        self.assertEqual(res,1)

    def test_010_main(self):
        args=['-h']
        with self.assertRaises(SystemExit) as context:
            kci_get_latest.main(args)
        self.assertEqual(context.exception.code,0)       
        
    def test_011_main(self):
        args=['']
        with self.assertRaises(SystemExit) as context:
            kci_get_latest.main(args)
        self.assertEqual(context.exception.code,2)       
        
    def test_012_main(self):
        args=['-a',"http://api.kernelci.org"]
        with self.assertRaises(SystemExit) as context:
            kci_get_latest.main(args)
        self.assertEqual(context.exception.code,2)       
        

if __name__=='__main__':
    unittest.main()
