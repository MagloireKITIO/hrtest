// recruitment/static/recruitment/js/recruitment_form.js

document.addEventListener('DOMContentLoaded', function() {
    const googleFormUrlField = document.querySelector('[name="google_form_url"]');
    const generateFormField = document.querySelector('[data-toggle="generateForm"]');
    const googleFormUrlContainer = googleFormUrlField.closest('.oh-input-group');

    function updateFormFieldsVisibility() {
        if (generateFormField.checked) {
            googleFormUrlContainer.style.display = 'none';
            googleFormUrlField.value = '';
        } else {
            googleFormUrlContainer.style.display = 'block';
        }
    }

    generateFormField.addEventListener('change', updateFormFieldsVisibility);
    updateFormFieldsVisibility();
});