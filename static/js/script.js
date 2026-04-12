// Vote Form Handler
document.addEventListener('DOMContentLoaded', function () {
    const voteForm = document.getElementById('voteForm');
    const submitVoteBtn = document.getElementById('submitVote');

    if (voteForm) {
        voteForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            const selectedCandidate = document.querySelector('input[name="candidate"]:checked');
            if (!selectedCandidate) {
                showAlert('Please select a candidate!', 'warning');
                return;
            }

            submitVoteBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Casting Vote...
            `;
            submitVoteBtn.disabled = true;

            const formData = new FormData();
            formData.append('candidate_id', selectedCandidate.value);
            formData.append('position', voteForm.dataset.position || 'General');

            try {
                const response = await fetch('/cast_vote', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    showAlert(result.message, 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 2000);
                } else {
                    showAlert(result.message || 'Something went wrong!', 'danger');
                }
            } catch (error) {
                showAlert('Network error. Please try again!', 'danger');
            } finally {
                submitVoteBtn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Cast Vote';
                submitVoteBtn.disabled = false;
            }
        });
    }

    // Add hover effects to candidate cards
    document.querySelectorAll('.candidate-card').forEach(card => {
        card.addEventListener('click', function () {
            const radio = this.querySelector('.vote-radio');
            if (radio) {
                radio.checked = true;
                radio.parentElement.classList.add('selected');
            }
        });
    });
});

// Alert Function
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Chart.js for Results (if needed)
function renderResultsChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                }
            }
        }
    });
}