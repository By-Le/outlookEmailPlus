"""
测试：导入含换行的 refresh_token 不再被截断
"""
import unittest
from unittest.mock import patch


class TestRefreshTokenNewlineMerge(unittest.TestCase):
    """验证 splitlines() 后的续行合并逻辑"""

    def _merge_lines(self, account_str: str) -> list:
        """复制 accounts.py 中的合并逻辑"""
        raw_lines = account_str.splitlines()
        merged_lines = []
        for _line in raw_lines:
            _stripped = _line.strip()
            if not _stripped:
                continue
            if merged_lines and "----" not in _stripped and not _stripped.startswith("#"):
                merged_lines[-1] += _stripped
            else:
                merged_lines.append(_stripped)
        return merged_lines

    def test_rt_with_newlines_gets_merged(self):
        """RT 含换行时，续行应合并回主行"""
        account_str = (
            "user@hotmail.com----pw----client-id----M.C559_SN1.0.U.-abc*wijEP\n"
            "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!\n"
            "z4Jo94dEJbyaaMSyhkQD0WUHHvrPFCXku!tZhxfi!jOooeH2gHE2IOmQS8NDI0s6nsuRY7SibuzIpswYA*\n"
            "zeCCz8x6QMA$"
        )
        lines = self._merge_lines(account_str)
        self.assertEqual(len(lines), 1, "应合并为 1 行")

        parts = lines[0].split("----")
        rt = "----".join(parts[3:])
        expected_rt = (
            "M.C559_SN1.0.U.-abc*wijEP"
            "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!"
            "z4Jo94dEJbyaaMSyhkQD0WUHHvrPFCXku!tZhxfi!jOooeH2gHE2IOmQS8NDI0s6nsuRY7SibuzIpswYA*"
            "zeCCz8x6QMA$"
        )
        self.assertEqual(rt, expected_rt, "RT 应完整无截断")

    def test_batch_import_with_wrapped_rt(self):
        """批量导入时，含换行的 RT 不影响第二条账号的解析"""
        account_str = (
            "user1@hotmail.com----pw1----cid1----short-rt\n"
            "user2@hotmail.com----pw2----cid2----M.C559_SN1.0.U.-abc*wijEP\n"
            "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqg\n"
            "longtailtokenend$"
        )
        lines = self._merge_lines(account_str)
        self.assertEqual(len(lines), 2, "应合并为 2 行（2 个账号）")

        # 第一条
        parts1 = lines[0].split("----")
        self.assertEqual(parts1[0].strip(), "user1@hotmail.com")
        self.assertEqual(parts1[3].strip(), "short-rt")

        # 第二条（RT 应完整）
        parts2 = lines[1].split("----")
        self.assertEqual(parts2[0].strip(), "user2@hotmail.com")
        rt2 = "----".join(parts2[3:])
        self.assertTrue(rt2.startswith("M.C559_SN1"))
        self.assertTrue(rt2.endswith("longtailtokenend$"))
        # RT = "M.C559_SN1.0.U.-abc*wijEP" + "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZp" + "longtailtokenend$"
        self.assertGreater(len(rt2), 100)

    def test_comment_lines_not_merged(self):
        """注释行不应被合并到上一行"""
        account_str = (
            "# This is a comment\n"
            "user@hotmail.com----pw----cid----rt-value\n"
            "# Another comment"
        )
        lines = self._merge_lines(account_str)
        # 合并后: 3 行（2 个注释 + 1 个账号），注释行不会被合并
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("#"))
        self.assertTrue(lines[1].startswith("user"))
        self.assertTrue(lines[2].startswith("#"))

    def test_empty_lines_skipped(self):
        """空行应被跳过"""
        account_str = "\n\nuser@hotmail.com----pw----cid----rt\n\n"
        lines = self._merge_lines(account_str)
        self.assertEqual(len(lines), 1)

    def test_rt_with_leading_spaces_merged(self):
        """RT 续行有前导空格时（常见于行宽折行），应正确合并"""
        account_str = (
            "user@hotmail.com----pw----cid----M.C559_SN1.0.U.-abc*wijEP                \n"
            "  bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!                \n"
            "  zeCCz8x6QMA$  "
        )
        lines = self._merge_lines(account_str)
        self.assertEqual(len(lines), 1)
        parts = lines[0].split("----")
        rt = "----".join(parts[3:])
        self.assertTrue(rt.endswith("zeCCz8x6QMA$"), f"RT 末尾应为完整: ...{rt[-30:]}")
        self.assertIn("bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!", rt)

    def test_parse_account_string_after_merge(self):
        """完整链路：合并后 parse_account_string 能正确解析"""
        account_str = (
            "onvoam11571l@hotmail.com----ni473830----9e5f94bc-e8a4-4e73-b8be-63364c29d753----M.C559_SN1.0.U.-CnlQlHCseit2zzQYcLU5jIWbRRwseUYhMT2Tr75w2WaYiMLnXPNg4v6ddst8op*wijEP\n"
            "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!\n"
            "z4Jo94dEJbyaaMSyhkQD0WUHHvrPFCXku!tZhxfi!jOooeH2gHE2IOmQS8NDI0s6nsuRY7SibuzIpswYA*\n"
            "GymV5ZcqLu63uKRbHm2pfiR2ddvXXl1TnfTfOnIwhdJ!1ie1iSYAiEFANKn9U7bGEd!u1bsncE0ceBX60nzeCCz8x6QMA$"
        )
        lines = self._merge_lines(account_str)
        self.assertEqual(len(lines), 1)

        # 模拟 parse_account_string
        parts = lines[0].split("----")
        self.assertGreaterEqual(len(parts), 4)
        self.assertEqual(parts[0].strip(), "onvoam11571l@hotmail.com")
        self.assertEqual(parts[1], "ni473830")
        self.assertEqual(parts[2].strip(), "9e5f94bc-e8a4-4e73-b8be-63364c29d753")
        rt = "----".join(parts[3:])
        self.assertTrue(rt.startswith("M.C559_SN1"))
        self.assertTrue(rt.endswith("zeCCz8x6QMA$"))
        # 确认 RT 完整（合并了所有续行，应远超第一行的长度）
        self.assertGreater(len(rt), 200, f"RT 应超过 200 字符，实际: {len(rt)}")


if __name__ == "__main__":
    unittest.main()
