import unittest
from shorts_studio import render


class RenderTests(unittest.TestCase):
    def test_validate_strips_paths(self):
        c = render.validate([{"name": "../../etc/a.mp4", "start": 1, "duration": 2}])
        self.assertEqual(c[0]["name"], "a.mp4")

    def test_validate_rejects_bad(self):
        for bad in ([], [{"name": "a.mp4", "duration": 0}],
                    [{"name": "a.mp4", "duration": 999}]):
            with self.assertRaises(ValueError):
                render.validate(bad)

    def test_command(self):
        clips = render.validate([{"name": "a.mp4", "start": 1, "duration": 2},
                                 {"name": "b.mp4", "duration": 3}])
        cmd = render.build_command(clips, ["a.mp4", "b.mp4"], [True, False], "o.mp4")
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("concat=n=2", fc)
        self.assertIn("anullsrc", fc)
        self.assertIn("crop=1080:1920", fc)
        self.assertEqual(cmd[-1], "o.mp4")


if __name__ == "__main__":
    unittest.main()
