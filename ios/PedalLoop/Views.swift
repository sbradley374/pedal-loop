import SwiftUI
import MapKit
import Charts
import UniformTypeIdentifiers
import PedalCore

extension Point { var coordinate: CLLocationCoordinate2D { .init(latitude: latitude, longitude: longitude) } }
private func distanceLabel(_ meters: Double) -> String {
    meters < 160 ? "\(Int(meters * 3.28084)) ft" : String(format: "%.1f mi", meters / 1609.344)
}
private func timeLabel(_ seconds: Double) -> String {
    let value = Int(max(0, seconds)); return String(format: "%d:%02d:%02d", value / 3600, value / 60 % 60, value % 60)
}

struct RootView: View {
    @EnvironmentObject private var planner: PlannerModel
    @EnvironmentObject private var ride: RideController
    @State private var tab = 0
    var body: some View {
        Group {
            if ride.hasRide { RideView() }
            else {
                TabView(selection: $tab) {
                    NavigationStack { PlannerView() }.tabItem { Label("Plan", systemImage: "map") }.tag(0)
                    NavigationStack { SavedRoutesView { tab = 0 } }.tabItem { Label("Saved", systemImage: "bookmark") }.tag(1)
                    NavigationStack { SettingsView() }.tabItem { Label("Server", systemImage: "network") }.tag(2)
                }
            }
        }
        .task {
            if !planner.credentials.address.isEmpty { await planner.configure(planner.credentials) }
        }
        .alert("Pedal Loop", isPresented: Binding(get: { planner.error != nil }, set: { if !$0 { planner.error = nil } })) {
            Button("OK") { planner.error = nil }
        } message: { Text(planner.error ?? "") }
    }
}

struct PlannerView: View {
    @EnvironmentObject private var planner: PlannerModel
    @EnvironmentObject private var ride: RideController
    @State private var camera: MapCameraPosition = .region(.init(center: .init(latitude: 41.8268, longitude: -71.4025), span: .init(latitudeDelta: 0.08, longitudeDelta: 0.08)))
    @State private var center = Point(41.8268, -71.4025)
    @State private var export = false
    @State private var showStart = false
    @State private var address = ""
    @State private var lookingUp = false
    @State private var addressTask: Task<Void, Never>?
    @State private var addressGeneration = UUID()
    private var start: Point { Point(planner.preferences.lat, planner.preferences.lon) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if ride.recovery != nil {
                    VStack(alignment: .leading, spacing: 10) {
                        Label("An unfinished ride is saved on this iPhone", systemImage: "arrow.counterclockwise")
                        HStack {
                            Button("Recover paused ride") { ride.restore() }.buttonStyle(.borderedProminent)
                            Button("Discard", role: .destructive) { ride.discardRecovery() }
                        }
                    }.padding().background(.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 16))
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("A good ride starts here.").font(.largeTitle.bold())
                    Text(planner.status).font(.subheadline).foregroundStyle(.secondary)
                }
                map
                if let message = ride.message { Text(message).font(.callout).foregroundStyle(.orange) }
                plannerControls
                if let selected = planner.selected { routeDetails(selected) }
                Text("Routes: © OpenStreetMap contributors · Elevation: Mapzen / AWS terrain sources. Apple Maps supplies the basemap.")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Pedal Loop").navigationBarTitleDisplayMode(.inline)
        .onChange(of: planner.preferences.regionID) { _, _ in camera = .region(.init(center: start.coordinate, span: .init(latitudeDelta: 0.10, longitudeDelta: 0.10))) }
        .onChange(of: planner.selected?.id) { _, _ in if planner.selected != nil { camera = .automatic } }
        .onChange(of: planner.preferences) { _, _ in addressTask?.cancel(); addressGeneration = UUID(); lookingUp = false }
        .onDisappear { addressTask?.cancel(); addressGeneration = UUID(); lookingUp = false }
        .fileExporter(isPresented: $export, document: GPXDocument(text: planner.selected?.route.gpx() ?? ""),
                      contentType: GPXDocument.kind, defaultFilename: "pedal-loop.gpx") { result in
            if case .failure(let error) = result { planner.error = error.localizedDescription }
        }
        .confirmationDialog("Start a navigation beta ride?", isPresented: $showStart, titleVisibility: .visible) {
            Button("Start GPS ride") { if let selected = planner.selected { ride.start(selected) } }
        } message: {
            Text("Mapped cues are approximate and may miss restrictions or complex junctions. Check signs and conditions. No automatic rerouting. Location continues during an active ride with the screen locked; end the ride to stop it.")
        }
    }
    private var map: some View {
        VStack(spacing: 0) {
            Map(position: $camera) {
                if let region = planner.regions.first(where: { $0.id == planner.preferences.regionID }),
                   let p = region.point, let radius = region.radiusM {
                    MapCircle(center: p.coordinate, radius: radius).foregroundStyle(.teal.opacity(0.06)).stroke(.teal.opacity(0.3), lineWidth: 1)
                }
                if let selected = planner.selected {
                    MapPolyline(coordinates: selected.route.points.map(\.coordinate)).stroke(.teal, lineWidth: 5)
                    if let p = selected.route.points.first { Marker("Route start", systemImage: "flag.checkered", coordinate: p.coordinate).tint(.teal) }
                } else { Marker("Requested start", coordinate: start.coordinate).tint(.orange) }
            }
            .mapControls { MapCompass(); MapScaleView() }
            .onMapCameraChange(frequency: .onEnd) { context in center = Point(context.region.center.latitude, context.region.center.longitude) }
            .overlay { if planner.selected == nil { Image(systemName: "plus").font(.title2).foregroundStyle(.primary).allowsHitTesting(false) } }
            .frame(height: 300).accessibilityLabel("Route planning map. Move the map and choose Use map center to set the start.")
            HStack {
                Button("Use map center", systemImage: "scope") { planner.useLocation(center) }
                Spacer()
                Button("My location", systemImage: "location") {
                    ride.locate { point in
                        planner.useLocation(point)
                        camera = .region(.init(center: point.coordinate, span: .init(latitudeDelta: 0.04, longitudeDelta: 0.04)))
                    }
                }
            }.font(.subheadline.weight(.semibold)).padding().disabled(planner.busy)
        }.background(.background, in: RoundedRectangle(cornerRadius: 20)).clipShape(RoundedRectangle(cornerRadius: 20))
    }
    private var plannerControls: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                TextField("Find a town or starting place", text: $address).textInputAutocapitalization(.words).submitLabel(.search).onSubmit(lookup)
                Button(action: lookup) { if lookingUp { ProgressView() } else { Image(systemName: "magnifyingglass") } }
                    .accessibilityLabel("Search places").disabled(lookingUp || address.trimmingCharacters(in: .whitespaces).isEmpty)
            }.padding(12).background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
            Picker("Cached road region", selection: Binding(get: { planner.preferences.regionID ?? "" }, set: { id in
                if let region = planner.regions.first(where: { $0.id == id }) { planner.choose(region) }
            })) {
                if planner.regions.isEmpty { Text("Connect a server").tag("") }
                ForEach(planner.regions) { Text($0.label).tag($0.id) }
            }
            Text(String(format: "Start: %.5f, %.5f", start.latitude, start.longitude)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
            HStack { Text("Ride distance").font(.headline); Spacer(); Text("\(Int(planner.preferences.miles)) mi").font(.title2.bold()) }
            Slider(value: $planner.preferences.miles, in: 5...75, step: 1).accessibilityLabel("Ride distance in miles")
            DisclosureGroup("Road and climbing preferences") {
                VStack(alignment: .leading, spacing: 14) {
                    Picker("Hills", selection: $planner.preferences.hills) {
                        Text("Balanced").tag("neutral"); Text("Flatter").tag("avoid"); Text("Hillier").tag("seek")
                    }.pickerStyle(.segmented)
                    Text("Avoid busy roads"); Slider(value: $planner.preferences.traffic, in: 0...1)
                    Text("Avoid stops"); Slider(value: $planner.preferences.stops, in: 0...1)
                    Toggle("Exclude major roads", isOn: $planner.preferences.avoidMajor)
                    Toggle("Only explicitly paved roads", isOn: $planner.preferences.strict)
                    Picker("Distance tolerance", selection: $planner.preferences.tolerance) {
                        ForEach([5.0, 10, 20, 30], id: \.self) { Text("±\(Int($0))%").tag($0) }
                    }
                    Toggle("Limit estimated climbing", isOn: Binding(get: { planner.preferences.maxAscent != nil }, set: { planner.preferences.maxAscent = $0 ? 1000 : nil }))
                    if planner.preferences.maxAscent != nil {
                        Stepper("Up to \(Int(planner.preferences.maxAscent ?? 1000)) ft", value: Binding(get: { planner.preferences.maxAscent ?? 1000 }, set: { planner.preferences.maxAscent = $0 }), in: 0...30000, step: 250)
                    }
                }.padding(.top, 8)
            }
            Text("Search stays inside the cached road region. Map coverage does not imply routing coverage.").font(.caption).foregroundStyle(.secondary)
        }
        .padding().background(.background, in: RoundedRectangle(cornerRadius: 20))
        .disabled(planner.busy)
        // The search/cancel button is outside the disabled preferences container.
        .safeAreaInset(edge: .bottom, spacing: 12) {
            Button {
                if planner.busy { planner.cancel() } else { planner.search() }
            } label: {
                HStack { if planner.busy { ProgressView().tint(.white) }; Text(planner.busy ? "Cancel search" : "Find my loop").font(.headline) }
                    .frame(maxWidth: .infinity).padding(8)
            }.buttonStyle(.borderedProminent).disabled(!planner.connected && !planner.busy)
        }
    }
    private func routeDetails(_ selected: SavedRoute) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Choose your loop").font(.title2.bold())
            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(Array(selected.result.routes.enumerated()), id: \.offset) { index, route in
                        Button { planner.routeIndex = index } label: {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("OPTION \(index + 1)").font(.caption.bold())
                                Text(String(format: "%.1f mi", route.distanceMiles)).font(.title2.bold())
                                Text(route.ascentFt.map { "\(Int($0)) ft climbing" } ?? "Climbing unavailable").font(.caption)
                            }.padding().foregroundStyle(index == planner.routeIndex ? Color.white : Color.primary)
                                .background(index == planner.routeIndex ? Color.teal : Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))
                        }.buttonStyle(.plain).accessibilityAddTraits(index == planner.routeIndex ? .isSelected : [])
                    }
                }
            }
            if let profile = selected.route.elevationProfile, !profile.isEmpty {
                Chart(Array(profile.enumerated()), id: \.offset) { pair in
                    if pair.element.count == 2 {
                        AreaMark(x: .value("Miles", pair.element[0]), y: .value("Feet", pair.element[1] * 3.28084)).foregroundStyle(.teal.opacity(0.2))
                        LineMark(x: .value("Miles", pair.element[0]), y: .value("Feet", pair.element[1] * 3.28084)).foregroundStyle(.teal)
                    }
                }.frame(height: 120).accessibilityLabel("Estimated terrain elevation profile")
            }
            Text("Major roads: \(Int(selected.route.majorRoadPct ?? 0))% · Unknown surface: \(Int(selected.route.unknownSurfacePct ?? 0))%")
                .font(.caption).foregroundStyle(.secondary)
            if let snap = selected.result.snapDistanceM, snap > 20 { Text("Route begins \(distanceLabel(snap)) from your chosen point. Travel to that start is not included.").font(.callout) }
            ForEach(selected.result.warnings, id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
            Button { showStart = true } label: { Label("Start ride", systemImage: "bicycle").font(.headline).frame(maxWidth: .infinity).padding(8) }
                .buttonStyle(.borderedProminent).disabled(!selected.result.isReal)
            HStack {
                Button("Save offline", systemImage: "arrow.down.circle") { planner.saveSelected() }
                Spacer()
                Button("Export GPX", systemImage: "square.and.arrow.up") { export = true }
            }.buttonStyle(.bordered)
            Button("Preview navigation without GPS", systemImage: "play.circle") { ride.start(selected, simulation: true) }.font(.subheadline)
            Text("Offline saves include route geometry and cues, not downloaded Apple basemaps. Mapped cues are approximate; automatic rerouting is not available.").font(.caption).foregroundStyle(.secondary)
        }.padding().background(.background, in: RoundedRectangle(cornerRadius: 20))
    }
    private func lookup() {
        guard !address.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        addressTask?.cancel(); let token = UUID(); addressGeneration = token; lookingUp = true
        let request = MKLocalSearch.Request(); request.naturalLanguageQuery = address
        addressTask = Task { @MainActor in
            defer { if addressGeneration == token { lookingUp = false } }
            do {
                let response = try await MKLocalSearch(request: request).start()
                guard !Task.isCancelled, addressGeneration == token else { return }
                guard let item = response.mapItems.first else { planner.error = "No matching place found."; return }
                let p = item.placemark.coordinate
                planner.useLocation(Point(p.latitude, p.longitude))
                camera = .region(.init(center: p, span: .init(latitudeDelta: 0.04, longitudeDelta: 0.04)))
            } catch { if !Task.isCancelled, addressGeneration == token { planner.error = error.localizedDescription } }
        }
    }
}

struct RideView: View {
    @EnvironmentObject private var ride: RideController
    @State private var camera: MapCameraPosition = .automatic
    @State private var ending = false
    @State private var cues = false
    private var current: NavigationUpdate? { ride.update }
    private var title: String {
        if current?.state == .arrived { return "Loop complete" }
        if ride.paused { return "Ride paused" }
        switch current?.state {
        case .offRoute: return "Off route · stop safely"
        case .weakGPS: return "Waiting for a reliable GPS fix"
        case .waiting: return "Head to the marked route start"
        case .onRoute: return current?.next?.instruction ?? "Follow the highlighted route"
        default: return ride.simulating ? "Navigation preview" : "Finding your position…"
        }
    }
    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Label(ride.simulating ? "SIMULATION · NOT LIVE GPS" : "RIDE BETA", systemImage: ride.simulating ? "play.circle" : "bicycle").font(.caption.bold())
                    Spacer()
                    Toggle("Voice cues", isOn: $ride.voice).labelsHidden().accessibilityLabel("Voice cues")
                }
                Text(title).font(.title2.bold()).fixedSize(horizontal: false, vertical: true)
                if !ride.paused, current?.state == .onRoute, let meters = current?.distanceToCue { Text("In \(distanceLabel(meters))").font(.title3.monospacedDigit()) }
                if current?.state == .offRoute { Text("Check the map and return to the route. Automatic rerouting is unavailable.").font(.subheadline) }
                if let message = ride.message { Text(message).font(.caption) }
            }.padding().frame(maxWidth: .infinity, alignment: .leading)
                .background(current?.state == .offRoute || current?.state == .weakGPS ? Color.orange.opacity(0.18) : Color.teal.opacity(0.12))
            Map(position: $camera) {
                if let active = ride.active {
                    MapPolyline(coordinates: active.route.points.map(\.coordinate)).stroke(.teal, lineWidth: 7)
                    if let start = active.route.points.first { Marker("Loop start / finish", systemImage: "flag.checkered", coordinate: start.coordinate) }
                }
                if let position = ride.position {
                    Annotation(ride.simulating ? "Simulated position" : "Your position", coordinate: position.coordinate) {
                        Image(systemName: "location.north.circle.fill").font(.largeTitle).foregroundStyle(.blue).background(.white, in: Circle())
                    }
                }
            }
            .mapControls { MapCompass(); MapScaleView() }
            .simultaneousGesture(DragGesture(minimumDistance: 10).onChanged { _ in ride.follow = false })
            .overlay(alignment: .bottomTrailing) {
                Button { ride.follow = true; recenter() } label: { Label("Recenter", systemImage: "location.fill").padding(10).background(.regularMaterial, in: Capsule()) }
                    .padding().accessibilityLabel("Recenter on ride position")
            }
            VStack(spacing: 14) {
                HStack {
                    metric("SPEED", ride.paused ? "—" : current?.speed.map { String(format: "%.1f", $0 * 2.236936) } ?? "—", "mph")
                    Spacer()
                    metric("RIDDEN", String(format: "%.2f", (current?.ridden ?? 0) / 1609.344), "mi")
                    Spacer()
                    metric("TO GO", ride.paused ? "—" : current?.remaining.map { String(format: "%.1f", $0 / 1609.344) } ?? "—", "mi")
                }
                HStack {
                    Text(timeLabel(ride.elapsed)).monospacedDigit()
                    Spacer()
                    Button("Cue sheet", systemImage: "list.bullet") { cues = true }
                }.font(.subheadline)
                HStack {
                    Button(ride.paused ? "Resume" : "Pause", systemImage: ride.paused ? "play.fill" : "pause.fill") {
                        if ride.paused { ride.resume() } else { ride.pause() }
                    }.buttonStyle(.borderedProminent).disabled(current?.state == .arrived)
                    Spacer()
                    Button("End ride", role: .destructive) { ending = true }.buttonStyle(.bordered)
                }.controlSize(.large)
            }.padding().background(.background)
        }
        .onChange(of: ride.position) { _, _ in if ride.follow { recenter() } }
        .onChange(of: ride.voice) { _, _ in ride.silence() }
        .confirmationDialog("End this ride?", isPresented: $ending, titleVisibility: .visible) {
            Button("End ride", role: .destructive) { ride.end() }
        } message: { Text("GPS tracking stops. A distance/time summary is saved locally; simulation summaries are not saved.") }
        .sheet(isPresented: $cues) {
            NavigationStack {
                List {
                    Section { Text("Approximate mapped cues. Check signs and current road access.").font(.callout) }
                    ForEach(Array((ride.active?.route.navigationCues ?? []).enumerated()), id: \.offset) { _, cue in
                        VStack(alignment: .leading) { Text(cue.instruction); Text(distanceLabel(cue.distanceM) + " from start").font(.caption).foregroundStyle(.secondary) }
                    }
                }.navigationTitle("Mapped cues").toolbar { Button("Done") { cues = false } }
            }
        }
    }
    private func metric(_ label: String, _ value: String, _ unit: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label).font(.caption2.bold()).foregroundStyle(.secondary)
            Text(value).font(.title2.bold().monospacedDigit()).minimumScaleFactor(0.6).lineLimit(1)
            Text(unit).font(.caption).foregroundStyle(.secondary)
        }.accessibilityElement(children: .combine)
    }
    private func recenter() {
        guard let position = ride.position else { return }
        camera = .camera(.init(centerCoordinate: position.coordinate, distance: 700,
                               heading: position.course >= 0 ? position.course : 0, pitch: 35))
    }
}

struct SavedRoutesView: View {
    @EnvironmentObject private var planner: PlannerModel
    @EnvironmentObject private var ride: RideController
    var open: () -> Void
    @State private var deletingHistory = false
    var body: some View {
        List {
            Section("Downloaded routes") {
                if planner.saved.isEmpty { Text("Save a route from Plan to keep its geometry and cues on this iPhone.").foregroundStyle(.secondary) }
                ForEach(planner.saved) { saved in
                    Button { planner.open(saved); open() } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(String(format: "%.1f mile loop", saved.route.distanceMiles)).font(.headline)
                            Text(saved.savedAt.formatted(date: .abbreviated, time: .shortened)).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }.onDelete(perform: planner.delete)
            }
            Section("Recent rides · stored on this iPhone") {
                ForEach(ride.history) { summary in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(String(format: "%.2f mi · %@", summary.miles, timeLabel(summary.seconds))).font(.headline)
                        Text(summary.date.formatted(date: .abbreviated, time: .shortened) + (summary.completed ? " · Completed" : " · Ended early")).font(.caption)
                    }
                }
                if !ride.history.isEmpty { Button("Delete ride history", role: .destructive) { deletingHistory = true } }
            }
        }.navigationTitle("Your rides")
            .confirmationDialog("Delete local ride summaries?", isPresented: $deletingHistory, titleVisibility: .visible) {
                Button("Delete history", role: .destructive) { ride.clearHistory() }
            }
    }
}

struct SettingsView: View {
    @EnvironmentObject private var planner: PlannerModel
    @State private var settings = ServerCredentials.empty
    var body: some View {
        Form {
            Section("Route engine") {
                TextField("https://your-server.trycloudflare.com", text: $settings.address).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                TextField("Username", text: $settings.username).textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("Beta password", text: $settings.password).textContentType(.password)
                Button { Task { await planner.configure(settings) } } label: {
                    HStack { Text("Connect and save"); if planner.connecting { Spacer(); ProgressView() } }
                }.disabled(planner.connecting)
                Text(planner.status).font(.caption)
            }
            Section("Local development") {
                Text("Paste the current HTTPS tunnel address. Your Mac and its route server must stay awake and online for new searches. A restarted quick tunnel gets a new address.")
                Text("Your password is stored in the iPhone Keychain. No credential is bundled with this app.")
            }
            Section("Maps, location and privacy") {
                Text("Apple Maps and place search send map/search requests to Apple. Route generation sends the chosen start and preferences to your server and its tunnel provider. Server results are retained under the server’s policy.")
                Text("Live GPS is processed on this iPhone. During a ride, location can continue in the background. Pause or End ride stops updates. Recovery stores the selected route and progress, not a GPS breadcrumb history. Recovery and downloaded routes are excluded from device backups.")
                Text("Downloaded routes work without the route server. Offline basemap downloads are not implemented. Approximate cues and background behavior need real-ride validation; automatic rerouting is not available.")
            }
            Section("Data attribution") {
                Link("OpenStreetMap contributors · ODbL", destination: URL(string: "https://www.openstreetmap.org/copyright")!)
                Link("Mapzen terrain source attribution", destination: URL(string: "https://github.com/tilezen/joerd/blob/master/docs/attribution.md")!)
            }
        }.navigationTitle("Server & privacy").onAppear { settings = planner.credentials }
    }
}

struct GPXDocument: FileDocument {
    static let kind = UTType(filenameExtension: "gpx") ?? .xml
    static var readableContentTypes: [UTType] { [kind, .xml] }
    var text: String
    init(text: String) { self.text = text }
    init(configuration: ReadConfiguration) throws { text = String(decoding: configuration.file.regularFileContents ?? Data(), as: UTF8.self) }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: Data(text.utf8)) }
}
