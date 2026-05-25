(function () {
  function findFieldContainer(input) {
    if (!input) {
      return null;
    }
    return (
      input.closest('.form-group') ||
      input.closest('.mb-3') ||
      input.closest('.field-group') ||
      input.closest('tr') ||
      input.parentElement
    );
  }

  function toggleOtherTypeField() {
    var labelTypeInput = document.querySelector('[name="label_type"]');
    var customTypeInput = document.querySelector('[name="custom_type"]');

    if (!labelTypeInput || !customTypeInput) {
      return;
    }

    var customTypeContainer = findFieldContainer(customTypeInput);
    var isOther = labelTypeInput.value === 'other';

    customTypeInput.required = isOther;

    if (customTypeContainer) {
      customTypeContainer.style.display = isOther ? '' : 'none';
    }

    if (!isOther) {
      customTypeInput.value = '';
    }
  }

  function init() {
    var labelTypeInput = document.querySelector('[name="label_type"]');
    if (!labelTypeInput) {
      return;
    }

    labelTypeInput.addEventListener('change', toggleOtherTypeField);
    toggleOtherTypeField();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
