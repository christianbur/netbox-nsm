/**
 * Generic visible_when handler for ObjectCustomObject forms.
 *
 * Any input/select with data-visible-when-field and data-visible-when-value
 * is shown only when the referenced field has the given value.
 *
 * data-visible-when-field: the [name] attribute of the controlling field
 * data-visible-when-value: the required value (string comparison)
 */
(function () {
  function findFieldContainer(el) {
    return (
      el.closest('.mb-3') ||
      el.closest('.form-group') ||
      el.closest('.field-group') ||
      el.closest('tr') ||
      el.parentElement
    );
  }

  function applyVisibility(triggerName) {
    var triggerEl = document.querySelector('[name="' + triggerName + '"]');
    var currentValue = triggerEl ? triggerEl.value : '';

    document.querySelectorAll('[data-visible-when-field="' + triggerName + '"]').forEach(function (el) {
      var requiredValue = el.getAttribute('data-visible-when-value');
      var container = findFieldContainer(el);
      var show = (currentValue === requiredValue);

      if (container) {
        container.style.display = show ? '' : 'none';
      }
      // Clear value when hidden so it doesn't get submitted
      if (!show) {
        if (el.tagName === 'SELECT') {
          el.selectedIndex = 0;
        } else {
          el.value = '';
        }
      }
    });
  }

  function init() {
    // Collect all unique trigger field names
    var triggers = new Set();
    document.querySelectorAll('[data-visible-when-field]').forEach(function (el) {
      triggers.add(el.getAttribute('data-visible-when-field'));
    });

    if (triggers.size === 0) return;

    triggers.forEach(function (triggerName) {
      // Apply initial state
      applyVisibility(triggerName);

      // Watch for changes on the controlling field
      var triggerEl = document.querySelector('[name="' + triggerName + '"]');
      if (triggerEl) {
        triggerEl.addEventListener('change', function () {
          applyVisibility(triggerName);
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
