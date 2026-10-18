import unittest
from publish import clean_ast, Extract

class ReaderTests(unittest.TestCase):
    def test_untrusted_urls_and_attributes(self):
        unsafe={'t':'Link','c':[['x',[],[['onclick','alert(1)']]],[{'t':'Str','c':'claim'}],['javascript:alert(1)','']]}
        self.assertEqual(clean_ast(unsafe)['t'],'Span')
        safe={'t':'Link','c':[['x',[],[['onclick','alert(1)']]],[{'t':'Str','c':'claim'}],['https://github.com/a/b','']]}
        self.assertEqual(clean_ast(safe)['c'][0],['',[],[]])
    def test_nested_contribution_boundaries(self):
        p=Extract();p.feed('<div id="contribution-1"><div><p>A &amp; B</p></div></div><div id="contribution-2">C</div>')
        self.assertEqual(set(p.pages),{1,2})
        self.assertIn('A &amp; B',p.pages[1])
        self.assertNotIn('contribution-2',p.pages[1])

if __name__=='__main__':unittest.main()
