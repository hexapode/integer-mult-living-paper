import json
import unittest
from progress import progress_data, render_progress

class ProgressTests(unittest.TestCase):
    def snapshot(self):
        return {'repo':'example/repo','finished_at':'2026-10-03T12:00:00Z',
            'sources':{'certificates/selected-result.json':json.dumps({'kappa':'2/1000'})},
            'frontier_history':[
                {'sha':'a','time':'2026-10-01T12:00:00Z','kappa':'1/1000','decimal':'0.001'},
                {'sha':'b','time':'2026-10-02T12:00:00Z','kappa':'2/1000','decimal':'0.002'},
                {'sha':'c','time':'2026-10-03T12:00:00Z','kappa':'2/1000','decimal':'0.002'}],
            'prs':[{'state':'merged','created_at':'2026-10-01T12:00:00Z','merged_at':'2026-10-02T12:00:00Z'},
                   {'state':'open','created_at':'2026-10-03T12:00:00Z','merged_at':None},
                   {'state':'closed','created_at':'2026-10-01T12:00:00Z','merged_at':None}]}
    def test_timeline_preserves_scope_and_removes_unchanged_checkpoints(self):
        data=progress_data(self.snapshot())
        self.assertEqual(len(data['frontier']),2)
        self.assertEqual(data['activity'][-1],{'date':'2026-10-03','submitted':2,'merged':1})
        page=render_progress(data)
        self.assertIn('blob/b/certificates/selected-result.json',page)
        self.assertIn('Selected conditional κ',page)
        self.assertNotIn('NaN',page)
    def test_history_cannot_disagree_with_selected_record(self):
        snap=self.snapshot();snap['frontier_history'][-1]['kappa']='3/1000'
        with self.assertRaisesRegex(ValueError,'pinned selected'):progress_data(snap)

    def test_tiny_gains_survive_float_rounding_and_retractions(self):
        snap=self.snapshot()
        snap['frontier_history'][0]['kappa']='1/1000'
        snap['frontier_history'][1]['kappa']='100000000000000000001/100000000000000000000000'
        snap['frontier_history']=snap['frontier_history'][:2]
        snap['sources']['certificates/selected-result.json']=json.dumps({'kappa':snap['frontier_history'][-1]['kappa']})
        page=render_progress(progress_data(snap))
        self.assertIn('+1.00000000e-23',page)
        self.assertIn('Full history',page)
        self.assertNotIn('NaN',page)
        snap['frontier_history'].reverse()
        snap['frontier_history'][0]['time']='2026-10-01T12:00:00Z'
        snap['frontier_history'][1]['time']='2026-10-02T12:00:00Z'
        snap['sources']['certificates/selected-result.json']=json.dumps({'kappa':'1/1000'})
        self.assertIn('-1.00000000e-23',render_progress(progress_data(snap)))
