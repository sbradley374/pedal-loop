import Testing
import Foundation
@testable import PedalCore

struct ContractTests {
    @Test func testDecodeBackendContractWithLegacyMissingCues() throws {
        let json = #"{"id":"example","routes":[{"coordinates":[[40,-105],[40.001,-105]],"distance_miles":5,"ascent_ft":null,"elevation_profile":[],"elevation":[[0,10],[0.069,null]]}],"source":{"source":"osm","label":"Roads","extra":123},"warnings":[],"snap_distance_m":3,"region_id":"test"}"#
        let result = try JSONDecoder().decode(RouteResult.self, from: Data(json.utf8))
        expectTrue(result.isReal)
        expectTrue(result.routes[0].isNavigable)
        expectNil(result.routes[0].navigationCues)
        expectTrue(result.routes[0].gpx().contains("<ele>10.0</ele>"))
        expectTrue(result.routes[0].gpx().contains("lat=\"40.0\" lon=\"-105.0\""))
        expectEqual(try JSONDecoder().decode(RouteResult.self, from: JSONEncoder().encode(result)), result)
    }
    @Test func testRequestUsesServerKeysAndRealRoads() throws {
        var request = SearchRequest(); request.regionID = "test"; request.avoidMajor = true; request.maxAscent = 500
        let json = try require(JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: Any])
        expectEqual(json["region_id"] as? String, "test")
        expectEqual(json["mode"] as? String, "osm")
        expectEqual(json["avoid_major"] as? Bool, true)
        expectEqual(json["max_ascent"] as? Double, 500)
    }
    @Test func testHTTPSOriginValidation() throws {
        expectEqual(try APIClient.validatedURL(" https://example.com/ ").host, "example.com")
        for invalid in ["http://example.com", "https://user:password@example.com", "https://example.com/api", "https://example.com?token=x", "https://example.com/#fragment", "bad url"] {
            #expect(throws: (any Error).self) { try APIClient.validatedURL(invalid) }
        }
    }
    @Test func testDecodeJobAndCatalog() throws {
        let job = try JSONDecoder().decode(RouteJob.self, from: Data(#"{"id":"123","status":"complete","result_id":"abc","cached":true}"#.utf8))
        expectEqual(job.resultID, "abc")
        let info = try JSONDecoder().decode(ServerInfo.self, from: Data(#"{"regions":[{"id":"p","label":"Providence","center":[41.8,-71.4],"radius_m":24000}],"active_region":"p"}"#.utf8))
        expectEqual(info.regions[0].point, Point(41.8, -71.4))
    }
}
