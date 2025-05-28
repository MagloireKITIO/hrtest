document.addEventListener('DOMContentLoaded', function() {
    $(document).on('click', '[id^=validateButton-]', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const stageId = $(this).data('stage-id');
        validateSelectedCandidates(stageId, 'validate');
    });
    
    $(document).on('click', '[id^=unvalidateButton-]', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const stageId = $(this).data('stage-id');
        validateSelectedCandidates(stageId, 'unvalidate');
    });
    // Fonction principale de validation/dévalidation
    function validateSelectedCandidates(stageId, action) {
        var selectedCandidates = [];
        $('.candidate-checkbox:checked').each(function() {
            selectedCandidates.push($(this).val());
        });
        
        if (selectedCandidates.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'Attention',
                text: 'Veuillez sélectionner au moins un candidat',
                confirmButtonText: 'Ok'
            });
            return;
        }
    
        const isValidating = action === 'validate';
        Swal.fire({
            title: isValidating ? 'Confirmer la validation' : 'Confirmer la dévalidation',
            text: isValidating ? 
                'Êtes-vous sûr de vouloir valider les candidats sélectionnés ?' : 
                'Êtes-vous sûr de vouloir annuler les candidats sélectionnés ?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: isValidating ? 'Oui, valider' : 'Oui, Annuler',
            cancelButtonText: 'Annuler'
        }).then((result) => {
            if (result.isConfirmed) {
                $.ajax({
                    url: '/recruitment/validate-selected-candidates/',
                    method: 'POST',
                    data: {
                        candidate_ids: selectedCandidates,
                        stage_id: stageId,
                        action: action,
                        csrfmiddlewaretoken: getCookie('csrftoken')
                    },
                    success: function(response) {
                        if (response.status === 'success') {
                            // Mettre à jour les classes visuelles
                            if (action === 'validate') {
                                selectedCandidates.forEach(id => {
                                    $(`.cand[data-candidate-id="${id}"]`).addClass('validated-candidate');
                                });
                            } else {
                                selectedCandidates.forEach(id => {
                                    $(`.cand[data-candidate-id="${id}"]`).removeClass('validated-candidate');
                                });
                            }
                            
                            // Décocher les cases
                            $('.candidate-checkbox:checked').prop('checked', false);
                            
                            Swal.fire({
                                icon: 'success',
                                title: 'Succès',
                                text: response.message,
                                timer: 1500
                            });
                            
                            $('#stageLoad' + stageId).click();
                        }
                    },
                    error: function(xhr, status, error) {
    console.error('Error:', error); // Pour le débogage
    Swal.fire({
        icon: 'error',
        title: 'Erreur',
        text: xhr.responseJSON && xhr.responseJSON.message ? 
              xhr.responseJSON.message : 
              'Une erreur s\'est produite lors de la communication avec le serveur'
    });
},
                });
            }
        });
    }

    // Fonction pour sélectionner les candidats validés (pour les recruteurs)
    function selectValidatedCandidates() {
        $('.candidate-checkbox').prop('checked', false);
        $('.validated-candidate .candidate-checkbox').prop('checked', true);
        
        const count = $('.validated-candidate .candidate-checkbox:checked').length;
        
        if (count > 0) {
            Swal.fire({
                icon: 'success',
                title: 'Sélection effectuée',
                text: `${count} candidat(s) validé(s) sélectionné(s)`,
                timer: 2000,
                showConfirmButton: false
            });
        } else {
            Swal.fire({
                icon: 'info',
                title: 'Information',
                text: 'Aucun candidat validé à sélectionner',
                timer: 2000,
                showConfirmButton: false
            });
        }
    }

    // Empêcher les demandeurs de faire des bulk updates
    const originalBulkStageUpdate = window.bulkStageUpdate;
    window.bulkStageUpdate = function(canIds, stageId, preStageId) {
        const isSelector = document.body.hasAttribute('data-is-selector');
        
        if (isSelector) {
            Swal.fire({
                icon: 'error',
                title: 'Non autorisé',
                text: 'Les demandeurs ne peuvent pas déplacer les candidats vers d\'autres étapes',
            });
            return;
        }
        
        if (typeof originalBulkStageUpdate === 'function') {
            originalBulkStageUpdate(canIds, stageId, preStageId);
        }
    };

    // Rendre les fonctions disponibles globalement
    window.selectValidatedCandidates = selectValidatedCandidates;
    window.validateSelectedCandidates = validateSelectedCandidates;
});