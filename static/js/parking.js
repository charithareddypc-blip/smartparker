// Real-time Fee Estimation and Slot Availability Checker
document.addEventListener('DOMContentLoaded', function () {
    const slotSelect = document.getElementById('selectSlot');
    const startInput = document.getElementById('inputStartTime');
    const endInput = document.getElementById('inputEndTime');
    const durationSpan = document.getElementById('estDuration');
    const rateSpan = document.getElementById('estRate');
    const feeSpan = document.getElementById('estFee');
    const alertDiv = document.getElementById('availabilityAlert');
    const submitBtn = document.getElementById('btnSubmitBooking');

    if (!slotSelect || !startInput || !endInput) return;

    let debounceTimer = null;

    function triggerEstimate() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(checkEstimateAndAvailability, 300);
    }

    slotSelect.addEventListener('change', triggerEstimate);
    startInput.addEventListener('change', triggerEstimate);
    endInput.addEventListener('change', triggerEstimate);

    async function checkEstimateAndAvailability() {
        const slotId = slotSelect.value;
        const startTime = startInput.value;
        const endTime = endInput.value;

        if (!slotId || !startTime || !endTime) {
            if (durationSpan) durationSpan.textContent = '—';
            if (rateSpan) rateSpan.textContent = '—';
            if (feeSpan) feeSpan.textContent = '$0.00';
            if (alertDiv) alertDiv.innerHTML = '<span class="text-muted">Select slot and time window to estimate fee.</span>';
            return;
        }

        const startDt = new Date(startTime);
        const endDt = new Date(endTime);

        if (endDt <= startDt) {
            if (alertDiv) {
                alertDiv.innerHTML = '<span class="text-danger fw-semibold"><i class="bi bi-exclamation-triangle-fill"></i> End time must be later than start time.</span>';
            }
            if (feeSpan) feeSpan.textContent = '$0.00';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        try {
            const url = `/api/reservations/estimate?slot_id=${encodeURIComponent(slotId)}&start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                if (durationSpan) durationSpan.textContent = `${data.duration_hours} hours`;
                if (rateSpan) rateSpan.textContent = `$${parseFloat(data.hourly_rate).toFixed(2)}/hr`;
                if (feeSpan) feeSpan.textContent = `$${parseFloat(data.estimated_amount).toFixed(2)}`;

                if (data.is_available) {
                    if (alertDiv) {
                        alertDiv.innerHTML = '<span class="text-success fw-semibold"><i class="bi bi-check-circle-fill"></i> Slot is available for the requested time range!</span>';
                    }
                    if (submitBtn) submitBtn.disabled = false;
                } else {
                    if (alertDiv) {
                        alertDiv.innerHTML = `<span class="text-danger fw-semibold"><i class="bi bi-x-circle-fill"></i> ${data.availability_message}</span>`;
                    }
                    if (submitBtn) submitBtn.disabled = true;
                }
            } else {
                if (alertDiv) {
                    alertDiv.innerHTML = `<span class="text-danger"><i class="bi bi-exclamation-circle"></i> ${data.message || 'Error validating slot.'}</span>`;
                }
                if (submitBtn) submitBtn.disabled = true;
            }
        } catch (error) {
            console.error('Error querying slot estimation API:', error);
        }
    }

    // Trigger initial check if values are pre-filled
    if (slotSelect.value) {
        checkEstimateAndAvailability();
    }
});
