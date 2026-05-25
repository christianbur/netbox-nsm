(function () {
  const MEMBER_FIELDS = [
    "groups",
    "addresses",
    "services",
    "applications",
    "labels",
    "zones",
    "sgts",
    "users",
  ];

  function findFieldContainer(field) {
    return (
      field.closest(".mb-3") ||
      field.closest(".form-group") ||
      field.closest(".field-group") ||
      field.parentElement
    );
  }

  function clearFieldValue(field) {
    if (!field) {
      return;
    }

    if (field.tomselect) {
      field.tomselect.clear(true);
      return;
    }

    if (field.tagName === "SELECT") {
      Array.from(field.options).forEach((option) => {
        option.selected = false;
      });
      field.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    field.value = "";
  }

  function setFieldEnabled(field, enabled) {
    if (!field) {
      return;
    }

    if (field.tomselect) {
      if (enabled) {
        field.tomselect.enable();
      } else {
        field.tomselect.disable();
      }
    }

    field.disabled = !enabled;
  }

  function applyGroupType(groupTypeValue) {
    const groupMemberTypeField = document.querySelector("[name='group_member_type']");
    if (groupMemberTypeField) {
      const groupMemberTypeContainer = findFieldContainer(groupMemberTypeField);
      const showGroupMemberType = groupTypeValue === "groups";

      if (groupMemberTypeContainer) {
        groupMemberTypeContainer.style.display = showGroupMemberType ? "" : "none";
      }

      if (!showGroupMemberType) {
        clearFieldValue(groupMemberTypeField);
      }
      setFieldEnabled(groupMemberTypeField, showGroupMemberType);
    }

    if (!groupTypeValue) {
      MEMBER_FIELDS.forEach((fieldName) => {
        const field = document.querySelector("[name='" + fieldName + "']");
        if (!field) {
          return;
        }

        const container = findFieldContainer(field);
        if (container) {
          container.style.display = "none";
        }
        clearFieldValue(field);
        setFieldEnabled(field, false);
      });
      return;
    }

    MEMBER_FIELDS.forEach((fieldName) => {
      const field = document.querySelector("[name='" + fieldName + "']");
      if (!field) {
        return;
      }

      const container = findFieldContainer(field);
      let enabled = false;

      if (groupTypeValue === "groups") {
        enabled = fieldName === "groups";
      } else {
        enabled = fieldName === groupTypeValue || fieldName === "groups";
      }

      if (container) {
        container.style.display = enabled ? "" : "none";
      }

      if (!enabled) {
        clearFieldValue(field);
      }
      setFieldEnabled(field, enabled);
    });
  }

  function getGroupTypeValue(groupTypeField) {
    if (!groupTypeField) {
      return "";
    }
    if (groupTypeField.tomselect) {
      return groupTypeField.tomselect.getValue();
    }
    return groupTypeField.value;
  }

  function initGroupTypeFilter() {
    const groupType = document.querySelector("[name='group_type']");
    if (!groupType) {
      return;
    }

    const update = function () {
      applyGroupType(getGroupTypeValue(groupType));
    };

    update();
    groupType.addEventListener("change", update);
    groupType.addEventListener("input", update);

    if (groupType.tomselect) {
      groupType.tomselect.on("change", update);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGroupTypeFilter);
  } else {
    initGroupTypeFilter();
  }
})();
