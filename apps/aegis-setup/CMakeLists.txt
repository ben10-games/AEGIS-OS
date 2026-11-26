qt_add_executable(aegis-setup main.cpp)
qt_add_qml_module(aegis-setup
    URI AegisSetup
    VERSION 1.0
    QML_FILES Main.qml
)
target_link_libraries(aegis-setup PRIVATE
    Qt6::Core Qt6::Gui Qt6::Network Qt6::Qml Qt6::Quick Qt6::QuickControls2)
install(TARGETS aegis-setup RUNTIME DESTINATION libexec/aegis)
