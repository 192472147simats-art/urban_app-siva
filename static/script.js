let selectedIssue = "";

// -------- Issue selection --------
function selectIssue(issue) {
    selectedIssue = issue;
    document.getElementById("issue").value = issue;

    document.querySelectorAll(".issue-grid div").forEach(div => {
        div.style.background = "#e7f1ff";
    });

    event.target.style.background = "#9ec5fe";

    const otherBox = document.getElementById("otherIssueBox");
    otherBox.style.display = (issue === "Other") ? "block" : "none";
}

// -------- Location detection --------
function getLocation() {
    if (!navigator.geolocation) {
        alert("Geolocation not supported by your browser");
        return;
    }
    navigator.geolocation.getCurrentPosition(success, error);
}

// -------- SUCCESS: Human-readable address --------
function success(position) {
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;

    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`)
        .then(res => res.json())
        .then(data => {
            const a = data.address;

            const locationText = [
                a.amenity,
                a.suburb || a.neighbourhood,
                a.city || a.town || a.village,
                a.state
            ].filter(Boolean).join(", ");

            document.getElementById("area").value = locationText;
        })
        .catch(() => {
            document.getElementById("area").value = "Location detected";
        });
}

// -------- ERROR --------
function error() {
    alert("Unable to retrieve your location");
}