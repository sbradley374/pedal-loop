import Foundation

public struct Point: Codable, Equatable, Sendable {
    public var latitude: Double
    public var longitude: Double
    public init(_ latitude: Double, _ longitude: Double) {
        self.latitude = latitude; self.longitude = longitude
    }
    public var isValid: Bool {
        latitude.isFinite && longitude.isFinite && abs(latitude) <= 85 && abs(longitude) <= 180
    }
    public func distance(to other: Point) -> Double {
        let r = Double.pi / 180
        let h = pow(sin((other.latitude - latitude) * r / 2), 2)
            + cos(latitude * r) * cos(other.latitude * r) * pow(sin((other.longitude - longitude) * r / 2), 2)
        return 6_371_000 * 2 * asin(sqrt(min(1, max(0, h))))
    }
}

public struct Cue: Codable, Equatable, Sendable {
    public var distanceM: Double
    public var coordinateIndex: Int
    public var instruction: String
    public init(distanceM: Double, coordinateIndex: Int, instruction: String) {
        self.distanceM = distanceM; self.coordinateIndex = coordinateIndex; self.instruction = instruction
    }
    enum CodingKeys: String, CodingKey {
        case distanceM = "distance_m", coordinateIndex = "coordinate_index", instruction
    }
}

public struct Route: Codable, Equatable, Sendable {
    public var coordinates: [[Double]]
    public var distanceMiles: Double
    public var ascentFt: Double?
    public var majorRoadPct: Double?
    public var unknownSurfacePct: Double?
    public var navigationCues: [Cue]?
    public var elevationProfile: [[Double]]?
    // One [distance in miles, nullable terrain height in meters] pair per coordinate.
    public var elevation: [[Double?]]?
    public var points: [Point] { coordinates.compactMap { $0.count == 2 ? Point($0[0], $0[1]) : nil } }
    public var isNavigable: Bool {
        points.count == coordinates.count && points.count >= 2 && points.allSatisfy(\.isValid)
            && zip(points, points.dropFirst()).contains { $0.distance(to: $1) > 0 }
    }
    public init(points: [Point], distanceMiles: Double, cues: [Cue] = []) {
        coordinates = points.map { [$0.latitude, $0.longitude] }
        self.distanceMiles = distanceMiles; navigationCues = cues
    }
    enum CodingKeys: String, CodingKey {
        case coordinates, distanceMiles = "distance_miles", ascentFt = "ascent_ft"
        case majorRoadPct = "major_road_pct", unknownSurfacePct = "unknown_surface_pct"
        case navigationCues = "navigation_cues"
        case elevationProfile = "elevation_profile", elevation
    }
    // Export from the downloaded geometry, even when the server is offline or the result expired.
    public func gpx() -> String {
        let track = points.enumerated().map { index, point in
            let height: Double? = elevation.flatMap {
                guard $0.indices.contains(index), $0[index].count == 2 else { return nil }
                return $0[index][1]
            }
            let ele = height.map { "<ele>\($0)</ele>" } ?? ""
            return "<trkpt lat=\"\(point.latitude)\" lon=\"\(point.longitude)\">\(ele)</trkpt>"
        }.joined(separator: "\n")
        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.1" creator="Pedal Loop" xmlns="http://www.topografix.com/GPX/1/1">
        <metadata><desc>Road geometry: OpenStreetMap contributors, ODbL. Elevation: Mapzen Terrain Tiles and source contributors, via AWS Open Data. Approximate cycling route; check current access and conditions.</desc></metadata>
        <trk><name>Pedal Loop</name><trkseg>\(track)</trkseg></trk></gpx>
        """
    }
}

public struct RouteSource: Codable, Equatable, Sendable { public var source: String; public var label: String? }
public struct RouteResult: Codable, Equatable, Identifiable, Sendable {
    public var id: String
    public var routes: [Route]
    public var source: RouteSource
    public var warnings: [String]
    public var snapDistanceM: Double?
    public var regionID: String?
    public var isReal: Bool { source.source == "osm" }
    enum CodingKeys: String, CodingKey {
        case id, routes, source, warnings, snapDistanceM = "snap_distance_m", regionID = "region_id"
    }
}
public struct Region: Codable, Identifiable, Equatable, Sendable {
    public var id: String
    public var label: String
    public var center: [Double]?
    public var radiusM: Double?
    public var point: Point? { guard let center, center.count == 2 else { return nil }; return Point(center[0], center[1]) }
    enum CodingKeys: String, CodingKey { case id, label, center, radiusM = "radius_m" }
}
public struct ServerInfo: Decodable, Sendable {
    public var regions: [Region]
    public var activeRegion: String?
    enum CodingKeys: String, CodingKey { case regions, activeRegion = "active_region" }
}
public struct SearchRequest: Codable, Equatable, Sendable {
    public var mode = "osm"
    public var regionID: String?
    public var lat = 41.8268
    public var lon = -71.4025
    public var miles = 20.0
    public var traffic = 0.8
    public var stops = 0.6
    public var hills = "neutral"
    public var strict = false
    public var avoidMajor = false
    public var tolerance = 10.0
    public var maxAscent: Double?
    public init() {}
    enum CodingKeys: String, CodingKey {
        case mode, regionID = "region_id", lat, lon, miles, traffic, stops, hills, strict, tolerance
        case avoidMajor = "avoid_major", maxAscent = "max_ascent"
    }
}
public struct RouteJob: Decodable, Sendable {
    public var id: String
    public var status: String
    public var resultID: String?
    public var error: String?
    enum CodingKeys: String, CodingKey { case id, status, error, resultID = "result_id" }
}
