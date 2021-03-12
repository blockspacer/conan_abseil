# About

modified conan package for abseil:

* uses `git clone`
* supports sanitizers, see [https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo#instrumented-gtest](https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo#instrumented-gtest)
* uses `llvm_tools` conan package in builds with `LLVM_USE_SANITIZER`, see https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo#instrumented-gtest
* uses `llvm_tools` conan package in builds with libc++ (will be instrumented if `LLVM_USE_SANITIZER` enabled)
* etc.

See `test_package/CMakeLists.txt` for usage example

NOTE: use `-s llvm_tools:build_type=Release` during `conan install`

## Before build

```bash
sudo apt-get update

# Tested with clang 6.0 and gcc 7
sudo apt-get -y install clang-6.0 g++-7 gcc-7

# llvm-config binary that coresponds to the same clang you are using to compile
export LLVM_CONFIG=/usr/bin/llvm-config-6.0
$LLVM_CONFIG --cxxflags
```

## Local build

```bash
conan remote add conan-center https://api.bintray.com/conan/conan/conan-center False

export PKG_NAME=abseil/master@conan/stable

(CONAN_REVISIONS_ENABLED=1 \
    conan remove --force $PKG_NAME || true)

CONAN_REVISIONS_ENABLED=1 \
    CONAN_VERBOSE_TRACEBACK=1 \
    CONAN_PRINT_RUN_COMMANDS=1 \
    CONAN_LOGGING_LEVEL=10 \
    GIT_SSL_NO_VERIFY=true \
    conan create . \
      conan/stable \
      -s build_type=Release \
      --profile clang \
      --build missing \
      --build cascade

CONAN_REVISIONS_ENABLED=1 \
    CONAN_VERBOSE_TRACEBACK=1 \
    CONAN_PRINT_RUN_COMMANDS=1 \
    CONAN_LOGGING_LEVEL=10 \
    conan upload $PKG_NAME \
      --all -r=conan-local \
      -c --retry 3 \
      --retry-wait 10 \
      --force

# clean build cache
conan remove "*" --build --force
```

## Build with sanitizers support

Use `-o llvm_tools:enable_tsan=True` and `-e *:compile_with_llvm_tools=True` like so:

```bash
export CC=$(find ~/.conan/data/llvm_tools/master/conan/stable/package/ -path "*bin/clang" | head -n 1)

export CXX=$(find ~/.conan/data/llvm_tools/master/conan/stable/package/ -path "*bin/clang++" | head -n 1)

export TSAN_OPTIONS="handle_segv=0:disable_coredump=0:abort_on_error=1:report_thread_leaks=0"

# make sure that env. var. TSAN_SYMBOLIZER_PATH points to llvm-symbolizer
# conan package llvm_tools provides llvm-symbolizer
# and prints its path during cmake configure step
# echo $TSAN_SYMBOLIZER_PATH
export TSAN_SYMBOLIZER_PATH=$(find ~/.conan/data/llvm_tools/master/conan/stable/package/ -path "*bin/llvm-symbolizer" | head -n 1)

# NOTE: NO `--profile` argument cause we use `CXX` env. var
CONAN_REVISIONS_ENABLED=1 \
    CONAN_VERBOSE_TRACEBACK=1 \
    CONAN_PRINT_RUN_COMMANDS=1 \
    CONAN_LOGGING_LEVEL=10 \
    GIT_SSL_NO_VERIFY=true \
    conan create . \
      conan/stable \
      -s build_type=Debug \
      -s compiler=clang \
      -s compiler.version=10 \
      -s compiler.libcxx=libc++ \
      -s llvm_tools:compiler=clang \
      -s llvm_tools:compiler.version=6.0 \
      -s llvm_tools:compiler.libcxx=libstdc++11 \
      --profile clang \
      -s llvm_tools:build_type=Release \
      -o llvm_tools:enable_tsan=True \
      -o llvm_tools:include_what_you_use=False \
      -e abseil:compile_with_llvm_tools=True \
      -e abseil:enable_llvm_tools=True \
      -e abseil_test_package:compile_with_llvm_tools=True \
      -e abseil_test_package:enable_llvm_tools=True \
      -o abseil:enable_tsan=True

# clean build cache
conan remove "*" --build --force
```

## conan Flow

```bash
conan source .
conan install --build missing --profile clang  -s build_type=Release .
conan build . --build-folder=.
conan package --build-folder=. .
conan export-pkg . conan/stable --settings build_type=Release --force --profile clang
conan test test_package abseil/master@conan/stable --settings build_type=Release --profile clang
```
