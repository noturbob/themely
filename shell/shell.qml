//@ pragma UseQApplication
import Quickshell
import Quickshell.Io
import QtQuick

ShellRoot {
    id: root

    property var themes: []
    property bool switcherOpen: false
    property bool dashboardOpen: false
    property string focusedOutput: ""

    function refresh() { listProc.running = true }

    Process {
        id: listProc
        command: ["themely", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.themes = JSON.parse(text) } catch (e) { console.warn("themely list:", e) }
            }
        }
    }

    Process {
        id: focusProc
        command: ["niri", "msg", "--json", "focused-output"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.focusedOutput = JSON.parse(text).name } catch (e) { root.focusedOutput = "" }
                root.switcherOpen = true
            }
        }
    }

    Component.onCompleted: refresh()

    IpcHandler {
        target: "switcher"
        function toggle(): void {
            if (root.switcherOpen) { root.switcherOpen = false; return }
            root.refresh()
            focusProc.running = true
        }
    }

    IpcHandler {
        target: "dashboard"
        function toggle(): void { root.dashboardOpen = !root.dashboardOpen }
    }

    LazyLoader {
        active: root.switcherOpen
        Switcher {
            themes: root.themes
            screen: Quickshell.screens.find(s => s.name === root.focusedOutput) ?? Quickshell.screens[0]
            onDismissed: root.switcherOpen = false
            onPicked: (slug, x, y) => { root.switcherOpen = false; reveal.start(slug, x, y) }
            onOpenDashboard: { root.switcherOpen = false; root.dashboardOpen = true }
        }
    }

    // Reveal {
    //     id: reveal
    //     onFinished: root.refresh()
    // }

    // LazyLoader {
    //     active: root.dashboardOpen
    //     Dashboard {
    //         themes: root.themes
    //         onDismissed: root.dashboardOpen = false
    //         onEdited: root.refresh()
    //     }
    // }
}
