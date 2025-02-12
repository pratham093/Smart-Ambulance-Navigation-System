// Declare global variables
var map;
var firstLocationSet = false;

var locationSetting; // ✅ Declare globally before DOMContentLoaded

document.addEventListener("DOMContentLoaded", function () {
    var mapElement = document.getElementById("map");

    if (!mapElement) {
        console.error("Map container not found! Ensure there is a div with id='map'");
        return;
    }

    var map = L.map('map').setView([19.105321, 72.830540], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // ✅ Assign function inside DOMContentLoaded
    locationSetting = function (lat, lon) {  
        let latInput = document.getElementById("latitude");
        let lonInput = document.getElementById("longitude");

        if (latInput) latInput.value = lat;
        if (lonInput) lonInput.value = lon;

        L.marker([lat, lon]).addTo(map)
            .bindPopup(`POI added at (${lat}, ${lon})`)
            .openPopup();
    };

    // ✅ Ensure it’s available globally
    window.locationSetting = locationSetting;
});


// document.addEventListener("DOMContentLoaded", function () {
//     // Initialize the map globally
//     map = L.map('map').setView([19.105321, 72.830540], 14);

//     L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
//         attribution: '&copy; OpenStreetMap contributors'
//     }).addTo(map);

//     // ✅ Attach locationSetting to window
//     window.locationSetting = function (lat, lon) {
//         let latInput = document.getElementById("latitude");
//         let lonInput = document.getElementById("longitude");

//         if (latInput) latInput.value = lat;
//         if (lonInput) lonInput.value = lon;

//         L.marker([lat, lon]).addTo(map)
//             .bindPopup(`POI added at (${lat}, ${lon})`)
//             .openPopup();

//         fetch('/add_poi', {
//             method: 'POST',
//             headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ x: lat, y: lon, id: `poi_${lat}_${lon}` })
//         })
//         .then(response => response.json())
//         .then(data => {
//             alert(data.message);
//         })
//         .catch(error => console.error('Error:', error));
//     };
// });

// ✅ Attach getLocation to window
window.getLocation = function () {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function (position) {
                console.log("Fetching live location:", position.coords.latitude, position.coords.longitude);

                let lat = position.coords.latitude;
                let lon = position.coords.longitude;

                document.getElementById("latitude").value = lat;
                document.getElementById("longitude").value = lon;

                addPOI(lat, lon);

                // Center the map only on the first location fetch
                if (!firstLocationSet) {
                    map.setView([lat, lon], 14);
                    firstLocationSet = true;
                }
            },
            function (error) {
                alert("Error fetching location: " + error.message);
            }
        );
    } else {
        alert("Geolocation is not supported by this browser.");
    }
};

// ✅ Function to add a POI marker to the map
function addPOI(lat, lon) {
    L.marker([lat, lon]).addTo(map)
        .bindPopup("Selected Location: " + lat + ", " + lon)
        .openPopup();
}
