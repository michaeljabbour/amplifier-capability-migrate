import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capability_film',ROOT/'scripts/capability.py')
capability=importlib.util.module_from_spec(spec)
spec.loader.exec_module(capability)

class FilmAssetTests(unittest.TestCase):
    def render(self,suffixes):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);film=root/'site/film';film.mkdir(parents=True)
            for suffix in suffixes:(film/('example'+suffix)).write_bytes(b'fixture')
            with patch.object(capability,'ROOT',root):
                return capability.render_film({'film':{'file':'example','heading':'Example','blurb':'Fictional fixture','seconds':10}})[0]
    def test_webm_only_has_no_broken_mp4_links(self):
        html=self.render(['.webm'])
        self.assertIn('film/example.webm',html)
        self.assertNotIn('example.mp4',html)
    def test_mp4_only_has_no_broken_webm_links(self):
        html=self.render(['.mp4'])
        self.assertIn('film/example.mp4',html)
        self.assertNotIn('example.webm',html)
    def test_both_formats_are_offered(self):
        html=self.render(['.mp4','.webm'])
        self.assertIn('type="video/mp4"',html)
        self.assertIn('type="video/webm"',html)
    def test_missing_media_does_not_advertise_a_film(self):
        self.assertEqual(self.render(['-poster.jpg','.vtt']),'')

if __name__=='__main__':unittest.main()
