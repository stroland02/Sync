# Which oasdiff release asset a machine runs, and what its archive unpacks to.
#
# A file of its own, sourced rather than executed, so the mapping is a function
# `tests/test_bootstrap_tools.py` can call with any `uname` pair from the one platform a test
# run happens to be on. Written inline, it was a literal `*windows_amd64.tar.gz` that blocked
# every macOS and Linux checkout at the third command of the README's Quick start.
#
# The patterns end in `.tar.gz` on purpose. oasdiff publishes `.apk`, `.deb` and `.rpm` beside
# the archive for Linux, and `gh release download` takes every asset its pattern matches.

oasdiff_asset() {
  local system="$1"
  local machine="$2"
  local os arch

  case "$system" in
    Linux) os=linux ;;
    Darwin) os=darwin ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT) os=windows ;;
    *)
      echo "oasdiff: no release asset is published for uname -s '$system'" >&2
      return 1
      ;;
  esac

  # One universal binary for macOS, so the architecture is not part of its name.
  if [ "$os" = darwin ]; then
    echo "*_darwin_all.tar.gz"
    return 0
  fi

  case "$machine" in
    x86_64|amd64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    *)
      echo "oasdiff: no release asset is published for uname -m '$machine'" >&2
      return 1
      ;;
  esac

  echo "*_${os}_${arch}.tar.gz"
}

oasdiff_binary() {
  case "$1" in
    MINGW*|MSYS*|CYGWIN*|Windows_NT) echo "oasdiff.exe" ;;
    *) echo "oasdiff" ;;
  esac
}
