import os, re, stat, json, fnmatch, platform, glob, traceback, shutil
from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment, RunEnvironment, python_requires
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.version import Version
from conans.tools import os_info
from functools import total_ordering

# if you using python less than 3 use from distutils import strtobool
from distutils.util import strtobool

conan_build_helper = python_requires("conan_build_helper/[~=0.0]@conan/stable")

# Users locally they get the 1.0.0 version,
# without defining any env-var at all,
# and CI servers will append the build number.
# USAGE
# version = get_version("1.0.0")
# BUILD_NUMBER=-pre1+build2 conan export-pkg . my_channel/release
def get_version(version):
    bn = os.getenv("BUILD_NUMBER")
    return (version + bn) if bn else version

class AbseilConan(conan_build_helper.CMakePackage):
    name = "abseil"

    description = "Abseil Common Libraries (C++) from Google"
    topics = ("algorithm", "container", "google", "common", "utility")

    homepage = "https://github.com/abseil/abseil-cpp"
    repo_url = "https://github.com/abseil/abseil-cpp.git"
    version = get_version("lts_2021_11_02")
    url = "https://github.com/conan-io/conan-center-index"

    license = "Apache-2.0"

    exports_sources = ["CMakeLists.txt", "patches/**"]
    generators = "cmake"
    short_paths = True

    settings = "os", "arch", "compiler", "build_type"

    options = {
        "enable_ubsan": [True, False],
        "enable_asan": [True, False],
        "enable_msan": [True, False],
        "enable_tsan": [True, False],
        "fPIC": [True, False]
    }

    default_options = {
        "enable_ubsan": False,
        "enable_asan": False,
        "enable_msan": False,
        "enable_tsan": False,
        "fPIC": True
    }

    _cmake = None

    # sets cmake variables required to use clang 10 from conan
    def _is_compile_with_llvm_tools_enabled(self):
      return self._environ_option("COMPILE_WITH_LLVM_TOOLS", default = 'false')

    # installs clang 10 from conan
    def _is_llvm_tools_enabled(self):
      return self._environ_option("ENABLE_LLVM_TOOLS", default = 'false')

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    def export_sources(self):
        self.copy("CMakeLists.txt")
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            self.copy(patch["patch_file"])

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.settings.compiler.cppstd:
            tools.check_min_cppstd(self, 11)

        lower_build_type = str(self.settings.build_type).lower()

        if lower_build_type != "release" and not self._is_llvm_tools_enabled():
            self.output.warn('enable llvm_tools for Debug builds')

        if self._is_compile_with_llvm_tools_enabled() and not self._is_llvm_tools_enabled():
            raise ConanInvalidConfiguration("llvm_tools must be enabled")

        if self.options.enable_ubsan \
           or self.options.enable_asan \
           or self.options.enable_msan \
           or self.options.enable_tsan:
            if not self._is_llvm_tools_enabled():
                raise ConanInvalidConfiguration("sanitizers require llvm_tools")

    def build_requirements(self):
        self.build_requires("cmake_platform_detection/master@conan/stable")
        self.build_requires("cmake_build_options/master@conan/stable")
        self.build_requires("cmake_helper_utils/master@conan/stable")

        if self.options.enable_tsan \
            or self.options.enable_msan \
            or self.options.enable_asan \
            or self.options.enable_ubsan:
          self.build_requires("cmake_sanitizers/master@conan/stable")

        # provides clang-tidy, clang-format, IWYU, scan-build, etc.
        if self._is_llvm_tools_enabled():
          self.build_requires("llvm_tools/master@conan/stable")

    def source(self):
        # tools.get(**self.conan_data["sources"][self.version])
        # extracted_dir = glob.glob('abseil-cpp-*/')[0]
        # os.rename(extracted_dir, self._source_subfolder)
        self.run('git clone -b {} --progress --depth 100 --recursive --recurse-submodules {} {}'.format(self.version, self.repo_url, self._source_subfolder))

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)
        #if not self.settings.compiler.cppstd:
        #    self._cmake.definitions["CMAKE_CXX_STANDARD"] = 11
        self._cmake.definitions["ABSL_ENABLE_INSTALL"] = True
        self._cmake.definitions["BUILD_TESTING"] = False
        self._cmake.definitions["ABSL_PROPAGATE_CXX_STD"] = True

        self._cmake.definitions["ENABLE_UBSAN"] = 'ON'
        if not self.options.enable_ubsan:
            self._cmake.definitions["ENABLE_UBSAN"] = 'OFF'

        self._cmake.definitions["ENABLE_ASAN"] = 'ON'
        if not self.options.enable_asan:
            self._cmake.definitions["ENABLE_ASAN"] = 'OFF'

        self._cmake.definitions["ENABLE_MSAN"] = 'ON'
        if not self.options.enable_msan:
            self._cmake.definitions["ENABLE_MSAN"] = 'OFF'

        self._cmake.definitions["ENABLE_TSAN"] = 'ON'
        if not self.options.enable_tsan:
            self._cmake.definitions["ENABLE_TSAN"] = 'OFF'

        self.add_cmake_option(self._cmake, "COMPILE_WITH_LLVM_TOOLS", self._is_compile_with_llvm_tools_enabled())

        self._cmake.configure()
        return self._cmake

    def build(self):
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            tools.patch(**patch)
        #for patch in self.conan_data.get("patches", {}).get(self.version, []):
        #    tools.patch(**patch)
        #tools.patch(patch_file = "patches/cmake-install.patch", base_path = self._source_subfolder)
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        self.copy("LICENSE", dst="licenses", src=self._source_subfolder)
        cmake = self._configure_cmake()
        cmake.install()
        cmake_folder = os.path.join(self.package_folder, "lib", "cmake")
        self._create_components_file_from_cmake_target_file(os.path.join(cmake_folder, "absl", "abslTargets.cmake"))
        tools.rmdir(cmake_folder)

    def _create_components_file_from_cmake_target_file(self, absl_target_file_path):
        components = {}

        abs_target_file = open(absl_target_file_path, "r")
        abs_target_content = abs_target_file.read()
        abs_target_file.close()

        cmake_functions = re.findall(r"(?P<func>add_library|set_target_properties)[\n|\s]*\([\n|\s]*(?P<args>[^)]*)\)", abs_target_content)
        for (cmake_function_name, cmake_function_args) in cmake_functions:
            cmake_function_args = re.split(r"[\s|\n]+", cmake_function_args, maxsplit=2)

            cmake_imported_target_name = cmake_function_args[0]
            cmake_target_nonamespace = cmake_imported_target_name.replace("absl::", "")
            potential_lib_name = "absl_" + cmake_target_nonamespace

            components.setdefault(potential_lib_name, {"cmake_target": cmake_target_nonamespace})

            if cmake_function_name == "add_library":
                cmake_imported_target_type = cmake_function_args[1]
                if cmake_imported_target_type in ["STATIC", "SHARED"]:
                    components[potential_lib_name]["libs"] = [potential_lib_name]
            elif cmake_function_name == "set_target_properties":
                target_properties = re.findall(r"(?P<property>INTERFACE_COMPILE_DEFINITIONS|INTERFACE_INCLUDE_DIRECTORIES|INTERFACE_LINK_LIBRARIES)[\n|\s]+(?P<values>.+)", cmake_function_args[2])
                for target_property in target_properties:
                    property_type = target_property[0]
                    if property_type == "INTERFACE_LINK_LIBRARIES":
                        values_list = target_property[1].replace('"', "").split(";")
                        for dependency in values_list:
                            if dependency.startswith("absl::"): # abseil targets
                                components[potential_lib_name].setdefault("requires", []).append(dependency.replace("absl::", "absl_"))
                            else: # system libs or frameworks
                                if self.settings.os == "Linux":
                                    if dependency == "Threads::Threads":
                                        components[potential_lib_name].setdefault("system_libs", []).append("pthread")
                                    elif "-lrt" in dependency:
                                        components[potential_lib_name].setdefault("system_libs", []).append("rt")
                                elif self.settings.os == "Windows":
                                    for system_lib in ["bcrypt", "advapi32", "dbghelp"]:
                                        if system_lib in dependency:
                                            components[potential_lib_name].setdefault("system_libs", []).append(system_lib)
                                elif self.settings.os == "Macos":
                                    for framework in ["CoreFoundation"]:
                                        if framework in dependency:
                                            components[potential_lib_name].setdefault("frameworks", []).append(framework)
                    elif property_type == "INTERFACE_COMPILE_DEFINITIONS":
                        values_list = target_property[1].replace('"', "").split(";")
                        for definition in values_list:
                            components[potential_lib_name].setdefault("defines", []).append(definition)

        # Save components informations in json file
        with open(self._components_helper_filepath, "w") as json_file:
            json.dump(components, json_file, indent=4)

    @property
    def _components_helper_filepath(self):
        return os.path.join(self.package_folder, "lib", "components.json")

    def package_info(self):
        self.cpp_info.names["cmake_find_package"] = "absl"
        self.cpp_info.names["cmake_find_package_multi"] = "absl"
        self._register_components()

    def _register_components(self):
        with open(self._components_helper_filepath, "r") as components_json_file:
            abseil_components = json.load(components_json_file)
            for conan_name, values in abseil_components.items():
                self._register_component(conan_name, values)

    def _register_component(self, conan_name, values):
        cmake_target = values["cmake_target"]
        self.cpp_info.components[conan_name].names["cmake_find_package"] = cmake_target
        self.cpp_info.components[conan_name].names["cmake_find_package_multi"] = cmake_target
        self.cpp_info.components[conan_name].libs = values.get("libs", [])
        self.cpp_info.components[conan_name].defines = values.get("defines", [])
        self.cpp_info.components[conan_name].system_libs = values.get("system_libs", [])
        self.cpp_info.components[conan_name].frameworks = values.get("frameworks", [])
        self.cpp_info.components[conan_name].requires = values.get("requires", [])
