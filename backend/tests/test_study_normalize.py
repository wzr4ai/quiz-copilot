from app.api import study


def test_normalize_choice_multi_contiguous_letters():
    # 连续字母的多选答案应拆分并排序
    assert study._normalize_answer("BCD", "choice_multi") == "B,C,D"
    assert study._normalize_answer("B,C,D", "choice_multi") == "B,C,D"


def test_normalize_choice_multi_mixed_delimiters():
    # 兼容中英文逗号和空格
    assert study._normalize_answer("b c，d", "choice_multi") == "B,C,D"
