// Doctor Availability Logic
// This script contains the function to fetch and display available appointment times

/**
 * Fetches available time slots for the selected doctor and date.
 */
function loadAvailableTimes() {
    const doctorDropdown = document.getElementById('doctorDropdown');
    const dateInput = document.getElementById('dateInput');
    const timeDropdown = document.getElementById('timeDropdown');
    const messageElement = document.getElementById('availabilityMessage');

    const doctorName = doctorDropdown.value;
    const dateValue = dateInput.value;

    // Reset dropdown and message
    timeDropdown.innerHTML = '<option value="">Loading...</option>';
    timeDropdown.disabled = true;
    messageElement.textContent = 'Checking availability...';
    messageElement.style.color = 'gray';

    if (!doctorName || !dateValue) {
        timeDropdown.innerHTML = '<option value="">-- Select Date and Doctor First --</option>';
        messageElement.textContent = 'Please select a doctor and date.';
        timeDropdown.disabled = true;
        return;
    }

    // Use URLSearchParams for clean API call construction
    const params = new URLSearchParams({ doctor: doctorName, date: dateValue });
    const url = `/api/doctor_availability?${params.toString()}`;

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            timeDropdown.innerHTML = '';
            const availableTimes = data.available_times;

            if (availableTimes && availableTimes.length > 0) {
                availableTimes.forEach(time => {
                    const option = document.createElement('option');
                    option.value = time;
                    option.textContent = time;
                    timeDropdown.appendChild(option);
                });
                timeDropdown.disabled = false;
                messageElement.textContent = `Found ${availableTimes.length} available slots.`;
                messageElement.style.color = 'var(--color-success)';
            } else {
                timeDropdown.innerHTML = '<option value="">No Slots Available</option>';
                messageElement.textContent = 'Dr. ' + doctorName + ' is fully booked on this date or is not working.';
                messageElement.style.color = 'var(--color-error)';
                timeDropdown.disabled = true;
            }
        })
        .catch(error => {
            console.error('Error fetching availability:', error);
            timeDropdown.innerHTML = '<option value="">Error Loading Times</option>';
            messageElement.textContent = 'An error occurred while checking availability.';
            messageElement.style.color = 'var(--color-error)';
            timeDropdown.disabled = true;
        });
}

// Ensure loadAvailableTimes is globally accessible if referenced in HTML
// (Note: The function is explicitly called from HTML in booking.html/edit_appointment.html)
// window.loadAvailableTimes = loadAvailableTimes; 
// The initial call for edit_appointment is still in edit_appointment.html script block