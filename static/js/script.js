const form = document.querySelector("form");
const image = document.getElementById("authImage");
const pointLayer = document.getElementById("pointLayer");
const pointsInput = document.getElementById("pointsInput");
const pointStatus = document.getElementById("pointStatus");
const pointCountInput = document.getElementById("pointCount");
const resetButton = document.getElementById("resetPoints");
const uploadedImage = document.getElementById("uploadedImage");
const sampleImages = document.querySelectorAll("input[name='selected_image']");
const waitMessage = document.getElementById("waitMessage");
const waitSecondsText = document.getElementById("waitSeconds");

let points = [];
let waitSeconds = Number(form.dataset.waitSeconds || 0);

function getNeededPointCount() {
    // Register page uses a select box and verify page uses a data value.
    if (pointCountInput) {
        return Number(pointCountInput.value);
    }

    return Number(form.dataset.pointCount);
}

function updatePointInput() {
    // The hidden input sends all selected points to Flask.
    pointsInput.value = JSON.stringify(points);
}

function updatePointStatus() {
    const neededCount = getNeededPointCount();
    const remainingCount = neededCount - points.length;

    if (remainingCount > 0) {
        pointStatus.textContent = "Click " + remainingCount + " more point(s) on the image.";
    } else {
        pointStatus.textContent = "All points selected.";
    }
}

function addPointMarker(x, y) {
    if (form.dataset.hidePoints === "yes") {
        return;
    }

    // This small circle helps the user see where the point was clicked.
    const marker = document.createElement("span");
    marker.className = "point";
    marker.style.left = x + "%";
    marker.style.top = y + "%";
    pointLayer.appendChild(marker);
}

function clearPoints() {
    points = [];
    pointLayer.innerHTML = "";
    updatePointInput();
    updatePointStatus();
}

function showWaitMessage() {
    if (!waitMessage) {
        return;
    }

    if (waitSeconds > 0) {
        waitMessage.style.display = "block";
        waitSecondsText.textContent = waitSeconds;
    } else {
        waitMessage.style.display = "none";
    }
}

function startWaitTimer() {
    if (waitSeconds <= 0) {
        showWaitMessage();
        return;
    }

    showWaitMessage();

    const timer = setInterval(function () {
        waitSeconds = waitSeconds - 1;
        showWaitMessage();

        if (waitSeconds <= 0) {
            clearInterval(timer);
            clearPoints();
        }
    }, 1000);
}

function changeImage(imagePath) {
    image.src = imagePath;
    clearPoints();
}

image.addEventListener("click", function (event) {
    if (waitSeconds > 0) {
        pointStatus.textContent = "Please wait until the timer completes.";
        return;
    }

    const neededCount = getNeededPointCount();

    if (points.length >= neededCount) {
        return;
    }

    const imageBox = image.getBoundingClientRect();
    const clickedX = event.clientX - imageBox.left;
    const clickedY = event.clientY - imageBox.top;

    const xPercent = Math.round((clickedX / imageBox.width) * 10000) / 100;
    const yPercent = Math.round((clickedY / imageBox.height) * 10000) / 100;

    points.push({
        x: xPercent,
        y: yPercent
    });

    addPointMarker(xPercent, yPercent);
    updatePointInput();
    updatePointStatus();
});

form.addEventListener("submit", function (event) {
    if (waitSeconds > 0) {
        event.preventDefault();
        pointStatus.textContent = "Please wait until the timer completes.";
        return;
    }

    const neededCount = getNeededPointCount();

    if (points.length !== neededCount) {
        event.preventDefault();
        pointStatus.textContent = "Please select exactly " + neededCount + " point(s).";
    }
});

resetButton.addEventListener("click", function () {
    clearPoints();
});

if (pointCountInput) {
    pointCountInput.addEventListener("change", function () {
        clearPoints();
    });
}

sampleImages.forEach(function (sampleImage) {
    sampleImage.addEventListener("change", function () {
        const imagePath = "/static/images/" + sampleImage.value;
        changeImage(imagePath);
    });
});

if (uploadedImage) {
    uploadedImage.addEventListener("change", function () {
        const file = uploadedImage.files[0];

        if (file) {
            const temporaryImagePath = URL.createObjectURL(file);
            changeImage(temporaryImagePath);
        }
    });
}

updatePointInput();
updatePointStatus();
startWaitTimer();
