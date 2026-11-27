# AEGIS OS applications (v3). Built in the 'apps' stage of image/Containerfile.v3 from
# locked inputs (rpms.in.yaml step apps-build); only the installed files reach the image.
cmake_minimum_required(VERSION 3.25)
project(aegis-apps LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Network Qml Quick QuickControls2 DBus)
qt_standard_project_setup(REQUIRES 6.5)

add_subdirectory(aegis-setup)
add_subdirectory(aegis-welcome)
