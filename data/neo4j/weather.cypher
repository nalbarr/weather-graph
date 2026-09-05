// Schema + data for the weather graph, mirroring model/weather.ttl exactly (8 flat City nodes,
// no relationships). Run via `make neo4j-migrate`.

CREATE CONSTRAINT city_name_unique IF NOT EXISTS
FOR (c:City) REQUIRE c.name IS UNIQUE;

MERGE (c:City {name: "Chicago"})
SET c.country = "United States", c.temperatureC = 21.0, c.condition = "Partly Cloudy", c.humidity = 58;

MERGE (c:City {name: "Paris"})
SET c.country = "France", c.temperatureC = 18.0, c.condition = "Cloudy", c.humidity = 72;

MERGE (c:City {name: "London"})
SET c.country = "United Kingdom", c.temperatureC = 15.0, c.condition = "Rainy", c.humidity = 81;

MERGE (c:City {name: "Cairo"})
SET c.country = "Egypt", c.temperatureC = 33.0, c.condition = "Sunny", c.humidity = 30;

MERGE (c:City {name: "Tokyo"})
SET c.country = "Japan", c.temperatureC = 24.0, c.condition = "Clear", c.humidity = 60;

MERGE (c:City {name: "Oslo"})
SET c.country = "Norway", c.temperatureC = 7.0, c.condition = "Snowy", c.humidity = 88;

MERGE (c:City {name: "Nairobi"})
SET c.country = "Kenya", c.temperatureC = 26.0, c.condition = "Partly Cloudy", c.humidity = 55;

MERGE (c:City {name: "Sydney"})
SET c.country = "Australia", c.temperatureC = 29.0, c.condition = "Sunny", c.humidity = 45;
