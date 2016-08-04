#!/usr/bin/python
###############################################################################
## @package test_kci_get_latest
# @brief Test the kci_get_latest module
#
import os,sys,re
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
        print "\n    Test default value: expect latest tag:"
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':None,'last':None}
        config = configuration.get_config(args)

        res=kci_get_latest.get_latest_tags(config)

        print "    Tag returned = ",res
        self.assertIsInstance(res,list)
        self.assertEqual(len(res),1)

    def test_002_get_latest_tags(self):
        print "\n    Test job only: expect latest tag matching job"
        print "    If job = mainline"
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':'mainline','last':None}
        config1 = configuration.get_config(args)

        res1=kci_get_latest.get_latest_tags(config1)

        print "    Tag returned = ",res1
        self.assertIsInstance(res1,list)
        self.assertEqual(len(res1),1)
        self.assertIn('mainline/',res1[0])

        print "    If job = stable"
        args['job']='stable'
        config2 = configuration.get_config(args)

        res2=kci_get_latest.get_latest_tags(config2)

        print "    Tag returned = ",res2
        self.assertIsInstance(res2,list)
        self.assertEqual(len(res2),1)
        self.assertIn('stable/',res2[0])


    def test_003_get_latest_tags(self):
        print "\n    Test last tag only: expect all tags from latest tag given"
        print "    If last = next/next-20160727"
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':None,'last':'next/next-20160727'}
        config = configuration.get_config(args)

        res=kci_get_latest.get_latest_tags(config)

        print "    Tags returned = ",res
        self.assertIsInstance(res,list)
        self.assertGreater(len(res),1)
        self.assertIn('next/next-20160727',res[len(res)-1])

    def test_004_get_latest_tags(self):
        print "\n    Test combination of job and last tag: expect all tags from latest tag given that match job"
        print "    If last = next/next-20160727 and job=mainline"
        args={'api':"http://api.kernelci.org",'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        config = configuration.get_config(args)

        res=kci_get_latest.get_latest_tags(config)

        print "    Tags returned = ",res
        self.assertIsInstance(res,list)
        self.assertGreater(len(res),1)
        for r in res:
            self.assertIn('mainline/',r)

    def test_005_run(self):
        print "\n    Check if mandatory token is given: Expect an assert"
        print "    Mandatory api not given also"
        args={'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        
        with self.assertRaises(ValueError) as context:
            kci_get_latest.run(args)
        self.assertTrue("No token found in config" in context.exception)       
        
        print "    Mandatory api is given"
        args={'api':"http://api.kernelci.org",'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        
        with self.assertRaises(ValueError) as context:
            kci_get_latest.run(args)
        self.assertTrue("No token found in config" in context.exception)       
        
    def test_006_run(self):
        print "\n    Check if mandatory api is given: Expect an assert"
        args={'token':"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'config':None,'section':None,'job':'mainline','last':'next/next-20160727'}
        
        with self.assertRaises(ValueError) as context:
            kci_get_latest.run(args)
        self.assertTrue("No api found in config" in context.exception)       
        
    def test_007_kci_get_latest(self):
        print "\n    Test default value: expect latest tag:"
        res=kci_get_latest.kci_get_latest("http://api.kernelci.org","bb4d438a-f412-4c65-9f7c-9daefd253ee7")
        print "    Tags returned = ",res
        self.assertIsInstance(res,list)
        self.assertEqual(len(res),1)
        self.assertTrue(re.match('([a-zA-Z0-9-_]+)/([a-zA-Z0-9-_]+)',res[0]))
        
    def test_008_kci_get_latest(self):
        print "\n    Test empty token. Expect returned error code 1"
        res=kci_get_latest.kci_get_latest("http://api.kernelci.org","")
        print "    Tags returned = ",res
        self.assertEqual(res,1)
        
    def test_009_kci_get_latest(self):
        print "\n    Test empty api. Expect returned error code 1"
        res=kci_get_latest.kci_get_latest("","bb4d438a-f412-4c65-9f7c-9daefd253ee7")
        print "    Tags returned = ",res
        self.assertEqual(res,1)

    def test_010_main(self):
        print "\n    Test input options : -h."
        print "    Expect: print usage and exit 0"
        args=['-h']
        with self.assertRaises(SystemExit) as context:
            res=kci_get_latest.main(args)
        self.assertEqual(context.exception.code,0)       
        
    def test_011_main(self):
        print "\n    Test input options : None"
        print "    Expect: print missing argument token error and exit 2"
        args=['']
        with self.assertRaises(SystemExit) as context:
            kci_get_latest.main(args)
        self.assertEqual(context.exception.code,2)       
        
    def test_012_main(self):
        print "\n    Test input options : -a http://api.kernelci.org"
        print "    Expect: print missing argument token error and exit 2"
        args=['-a',"http://api.kernelci.org"]
        with self.assertRaises(SystemExit) as context:
            kci_get_latest.main(args)
        self.assertEqual(context.exception.code,2)       

    def test_013_main(self):
        print "\n    Test input options : -t bb4d438a-f412-4c65-9f7c-9daefd253ee7"
        print "    Expect: print missing argument api error and exit 2"
        args=['-t',"bb4d438a-f412-4c65-9f7c-9daefd253ee7"]
        with self.assertRaises(SystemExit) as context:
            kci_get_latest.main(args)
        self.assertEqual(context.exception.code,2)       
        
    def test_014_main(self):
        print "\n    Test input options : -a http://api.kernelci.org -t bb4d438a-f412-4c65-9f7c-9daefd253ee7"
        print "    Expect: print last tag and return 0"
        args=['-a',"http://api.kernelci.org",'-t',"bb4d438a-f412-4c65-9f7c-9daefd253ee7"]
        res=kci_get_latest.main(args)
        self.assertEqual(res,0)       
        
    def test_015_main(self):
        print "\n    Test input options : -a http://api.kernelci.org -t bb4d438a-f412-4c65-9f7c-9daefd253ee7 -j mainline -l next/next-20160727"
        print "    Expect: print lasts tags matching mainline from tag next/next-20160727 and return 0"
        args=['-a',"http://api.kernelci.org",'-t',"bb4d438a-f412-4c65-9f7c-9daefd253ee7",'-j',"mainline",'-l',"next/next-20160727"]
        res=kci_get_latest.main(args)
        self.assertEqual(res,0)       
        
        
        

if __name__=='__main__':
    #unittest.main()
    #f_log=open("test_kci_get_latest.log","w")
    #suite = unittest.TestLoader().loadTestsFromTestCase(test_kci_get_latest)
    #unittest.TextTestRunner(f_log,verbosity=2).run(suite)
    #f_log.close()
    suite = unittest.TestLoader().loadTestsFromTestCase(test_kci_get_latest)
    unittest.TextTestRunner(verbosity=3).run(suite)
