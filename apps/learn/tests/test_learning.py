import http.client
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import NODES, PATHS, GLOSSARY
from sources import source_for, validate_sources
from experiments import LABS, run_lab
from traces import SCENARIOS, make_trace
from server import Handler, ThreadingHTTPServer


class CurriculumTests(unittest.TestCase):
    def test_tree_and_cross_references(self):
        ids = {n['id'] for n in NODES}
        self.assertEqual(len(ids), len(NODES))
        self.assertEqual([n['id'] for n in NODES if n['parent'] is None], ['system'])
        for n in NODES:
            self.assertTrue(n['code'])
            chain = set()
            at = n
            while at['parent']:
                self.assertNotIn(at['id'], chain)
                chain.add(at['id'])
                at = next(x for x in NODES if x['id'] == at['parent'])
            for term in n['terms']:
                self.assertIn(term, GLOSSARY)
            for item in n['inputs'] + n['outputs']:
                self.assertIn(item.get('from', item.get('to')), ids)
        for p in PATHS:
            self.assertTrue(set(p['nodes']) <= ids)

    def test_all_source_symbols_exist(self):
        self.assertEqual(len(validate_sources()), len([n for n in NODES if n['source']]))
        with self.assertRaises(ValueError):
            source_for('../../.env')

    def test_all_scenarios_map_to_pseudocode_and_finish(self):
        nodes = {n['id']:n for n in NODES}
        for scenario in SCENARIOS:
            trace = make_trace(scenario['id'])
            self.assertEqual(trace['kind'], 'teaching')
            self.assertTrue(any(s['wait'] for s in trace['steps']))
            for step in trace['steps']:
                self.assertGreaterEqual(step['line'], 1)
                self.assertLessEqual(step['line'], len(nodes[step['node']]['code']), step['node'])
            for a,b in zip(trace['steps'], trace['steps'][1:]):
                self.assertEqual(a['state_after'], b['state_before'])

    def test_scenario_differences(self):
        text = json.dumps(make_trace('empty_retrieval'), ensure_ascii=False)
        self.assertIn('below_similarity_threshold', text)
        text = json.dumps(make_trace('missing_signal'), ensure_ascii=False)
        self.assertIn('not_comparable', text)
        trace = make_trace('budget_limit')
        self.assertEqual(max(s['state_after'].get('tool_calls_in_round',0) for s in trace['steps']), 3)
        self.assertIn('999', json.dumps(make_trace('tool_failure')))


class ExperimentTests(unittest.TestCase):
    def test_filter_respects_status_scope_and_alias(self):
        r=run_lab('filter',{})
        self.assertEqual([x[0] for x in r['output']], ['A','D'])
        r=run_lab('filter',{'include_candidates':True})
        self.assertEqual([x[0] for x in r['output']], ['A','B','D'])
        r=run_lab('filter',{'intent':'optimization','target_role':'title'})
        self.assertEqual([x[0] for x in r['output']], ['C','D'])

    def test_similarity_and_empty_inputs(self):
        self.assertEqual(run_lab('similarity',{})['output'], {'lexical_score':.4,'combined_score':.74})
        self.assertEqual(run_lab('similarity',{'left':'','right':'abc'})['output']['lexical_score'],0)

    def test_missing_is_distinct_from_zero(self):
        missing=run_lab('scores',{'vision_available':False})['output']
        zero=run_lab('scores',{'vision_score':0})['output']
        self.assertIsNone(missing['vision'])
        self.assertEqual(missing['available_weight'],40)
        self.assertEqual(missing['total'],100)
        self.assertEqual(zero['vision'],0)
        self.assertEqual(zero['available_weight'],75)
        self.assertLess(zero['total'],missing['total'])
        self.assertEqual(run_lab('scores',{})['output']['total'],90.67)

    def test_counterfactuals(self):
        self.assertEqual(len(run_lab('budget',{})['output']['calls']),3)
        self.assertEqual(len(run_lab('budget',{'remove_limit':True})['output']['calls']),6)
        self.assertEqual(run_lab('revision',{})['output'],['新正式图'])
        self.assertEqual(run_lab('revision',{'check_revision':False})['output'],['旧正式图','新正式图'])

    def test_trace_is_original_lines_and_balanced_calls(self):
        for lab in LABS:
            result=run_lab(lab['id'],{})
            source=result['source']
            for step in result['steps']:
                self.assertEqual(step['code'],source['code'].splitlines()[step['line']-source['start']])
                self.assertTrue(step['stack'])
            self.assertTrue(any(s['event']=='return' for s in result['steps']))
            self.assertTrue(any(s['event']=='line' for s in result['steps']))

    def test_reject_unsafe_and_out_of_range_inputs(self):
        for lab,values in [('scores',{'vision_score':float('nan')}),('scores',{'vision_score':True}),('scores',{'attention_available':'yes'}),('budget',{'limit':1.5}),('similarity',{'left':'x'*81}),('filter',{'code':'print(1)'}),('unknown',{})]:
            with self.assertRaises(ValueError):
                run_lab(lab,values)

    def test_experiments_do_not_use_network_or_write_files(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')), patch.object(Path,'write_text',side_effect=AssertionError('write forbidden')):
            for lab in LABS:
                run_lab(lab['id'],{})


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def request(self,path,method='GET',body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        conn.request(method,path,body,headers or {})
        response=conn.getresponse()
        result=(response.status,response.read())
        conn.close()
        return result

    def test_pages_and_api(self):
        for path in ['/','/app.js','/styles.css','/api/health','/api/catalog','/api/source?id=scores','/api/trace?scenario=tool_failure','/flow-overview.html']:
            self.assertEqual(self.request(path)[0],200,path)
        status,body=self.request('/api/lab','POST',json.dumps({'id':'scores'}),{'Content-Type':'application/json'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['output']['total'],90.67)

    def test_reject_arbitrary_paths_origins_and_code(self):
        self.assertEqual(self.request('/%2e%2e/server.py')[0],404)
        self.assertEqual(self.request('/api/source?id=../../.env')[0],400)
        self.assertEqual(self.request('/api/health',headers={'Host':'attacker.test'})[0],403)
        self.assertEqual(self.request('/api/lab','POST','{}',{'Content-Type':'application/json','Origin':'https://attacker.test'})[0],403)
        self.assertEqual(self.request('/api/lab','POST','{}',{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('/api/lab','POST','[]',{'Content-Type':'application/json'})[0],400)


if __name__=='__main__':
    unittest.main(verbosity=2)
