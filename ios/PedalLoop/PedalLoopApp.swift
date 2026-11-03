import SwiftUI

@main struct PedalLoopApp: App {
    @StateObject private var planner = PlannerModel()
    @StateObject private var ride = RideController()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(planner).environmentObject(ride)
                .tint(Color(red: 0.06, green: 0.40, blue: 0.32))
                .onChange(of: scenePhase) { _, phase in if phase == .background { ride.didEnterBackground() } }
        }
    }
}
