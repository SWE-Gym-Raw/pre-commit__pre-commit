from __future__ import annotations

import multiprocessing
import os.path
import sys
from unittest import mock

import pytest

import pre_commit.constants as C
from pre_commit import lang_base
from pre_commit import parse_shebang
from pre_commit.prefix import Prefix
from pre_commit.util import CalledProcessError


@pytest.fixture
def find_exe_mck():
    with mock.patch.object(parse_shebang, 'find_executable') as mck:
        yield mck


@pytest.fixture
def homedir_mck():
    def fake_expanduser(pth):
        assert pth == '~'
        return os.path.normpath('/home/me')

    with mock.patch.object(os.path, 'expanduser', fake_expanduser):
        yield


def test_exe_exists_does_not_exist(find_exe_mck, homedir_mck):
    find_exe_mck.return_value = None
    assert lang_base.exe_exists('ruby') is False


def test_exe_exists_exists(find_exe_mck, homedir_mck):
    find_exe_mck.return_value = os.path.normpath('/usr/bin/ruby')
    assert lang_base.exe_exists('ruby') is True


def test_exe_exists_false_if_shim(find_exe_mck, homedir_mck):
    find_exe_mck.return_value = os.path.normpath('/foo/shims/ruby')
    assert lang_base.exe_exists('ruby') is False


def test_exe_exists_false_if_homedir(find_exe_mck, homedir_mck):
    find_exe_mck.return_value = os.path.normpath('/home/me/somedir/ruby')
    assert lang_base.exe_exists('ruby') is False


def test_exe_exists_commonpath_raises_ValueError(find_exe_mck, homedir_mck):
    find_exe_mck.return_value = os.path.normpath('/usr/bin/ruby')
    with mock.patch.object(os.path, 'commonpath', side_effect=ValueError):
        assert lang_base.exe_exists('ruby') is True


def test_exe_exists_true_when_homedir_is_slash(find_exe_mck):
    find_exe_mck.return_value = os.path.normpath('/usr/bin/ruby')
    with mock.patch.object(os.path, 'expanduser', return_value=os.sep):
        assert lang_base.exe_exists('ruby') is True


def test_basic_get_default_version():
    assert lang_base.basic_get_default_version() == C.DEFAULT


def test_basic_health_check():
    assert lang_base.basic_health_check(Prefix('.'), 'default') is None


def test_failed_setup_command_does_not_unicode_error():
    script = (
        'import sys\n'
        "sys.stderr.buffer.write(b'\\x81\\xfe')\n"
        'raise SystemExit(1)\n'
    )

    # an assertion that this does not raise `UnicodeError`
    with pytest.raises(CalledProcessError):
        lang_base.setup_cmd(Prefix('.'), (sys.executable, '-c', script))


def test_assert_no_additional_deps():
    with pytest.raises(AssertionError) as excinfo:
        lang_base.assert_no_additional_deps('lang', ['hmmm'])
    msg, = excinfo.value.args
    assert msg == (
        'for now, pre-commit does not support additional_dependencies for '
        'lang -- '
        "you selected `additional_dependencies: ['hmmm']`"
    )


def test_target_concurrency_normal():
    with mock.patch.object(multiprocessing, 'cpu_count', return_value=123):
        with mock.patch.dict(os.environ, {}, clear=True):
            assert lang_base.target_concurrency() == 123


def test_target_concurrency_testing_env_var():
    with mock.patch.dict(
            os.environ, {'PRE_COMMIT_NO_CONCURRENCY': '1'}, clear=True,
    ):
        assert lang_base.target_concurrency() == 1


def test_target_concurrency_on_travis():
    with mock.patch.dict(os.environ, {'TRAVIS': '1'}, clear=True):
        assert lang_base.target_concurrency() == 2


def test_target_concurrency_cpu_count_not_implemented():
    with mock.patch.object(
            multiprocessing, 'cpu_count', side_effect=NotImplementedError,
    ):
        with mock.patch.dict(os.environ, {}, clear=True):
            assert lang_base.target_concurrency() == 1


def test_shuffled_is_deterministic():
    seq = [str(i) for i in range(10)]
    expected = ['4', '0', '5', '1', '8', '6', '2', '3', '7', '9']
    assert lang_base._shuffled(seq) == expected


def test_xargs_require_serial_is_not_shuffled():
    ret, out = lang_base.run_xargs(
        ('echo',), [str(i) for i in range(10)],
        require_serial=True,
        color=False,
    )
    assert ret == 0
    assert out.strip() == b'0 1 2 3 4 5 6 7 8 9'