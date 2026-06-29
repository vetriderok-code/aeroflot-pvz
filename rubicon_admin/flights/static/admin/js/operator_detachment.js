(function () {
    'use strict';

    const DETACHMENT = 'detachment';
    const PROMPT_TEXT = 'Куда перемещаем?';

    function changelistForm() {
        return document.getElementById('changelist-form');
    }

    function formPrefixForSelect(select) {
        const match = select.name.match(/^(form-\d+)-placement_zone$/);
        return match ? match[1] : null;
    }

    function profileIdForRow(row) {
        if (!row) {
            return null;
        }
        const idInput = row.querySelector('input[name$="-id"]');
        return idInput ? idInput.value : null;
    }

    function profileIdForSelect(select) {
        const prefix = formPrefixForSelect(select);
        if (prefix) {
            const idInput = document.querySelector('input[name="' + prefix + '-id"]');
            if (idInput && idInput.value) {
                return idInput.value;
            }
        }
        return profileIdForRow(select.closest('tr'));
    }

    function ensureDestInput(formEl, profileId, value) {
        if (!formEl || !profileId) {
            return false;
        }
        const name = 'detachment_dest_' + profileId;
        let input = formEl.querySelector('input[name="' + name + '"]');
        if (!input) {
            input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            formEl.appendChild(input);
        }
        input.value = value;
        return true;
    }

    function showDestHint(select, destination) {
        const host = select.parentNode;
        if (!host) {
            return;
        }
        let hint = host.querySelector('.detachment-dest-hint');
        if (!hint) {
            hint = document.createElement('span');
            hint.className = 'detachment-dest-hint';
            hint.style.cssText = 'display:block;font-size:11px;color:#666;margin-top:2px;';
            host.appendChild(hint);
        }
        hint.textContent = '→ ' + destination;
    }

    function syncDestForSelect(select) {
        const destination = (select.dataset.detachmentDest || '').trim();
        if (!destination) {
            return;
        }
        const formEl = changelistForm();
        const profileId = profileIdForSelect(select);
        if (ensureDestInput(formEl, profileId, destination)) {
            showDestHint(select, destination);
        }
    }

    function bindPlacementSelect(select) {
        if (select.dataset.detachmentBound === '1') {
            return;
        }
        select.dataset.detachmentBound = '1';
        select.dataset.initialZone = select.value;

        select.addEventListener('change', function () {
            const initialZone = select.dataset.initialZone || '';
            delete select.dataset.detachmentDest;

            if (select.value !== DETACHMENT || initialZone === DETACHMENT) {
                return;
            }

            const destination = (window.prompt(PROMPT_TEXT) || '').trim();
            if (!destination) {
                select.value = initialZone;
                window.alert('Укажите, куда перемещаем. Перевод на отрыв отменён.');
                return;
            }

            select.dataset.detachmentDest = destination;
            syncDestForSelect(select);
        });
    }

    function bindChangelistSubmit() {
        const formEl = changelistForm();
        if (!formEl || formEl.dataset.detachmentSubmitBound === '1') {
            return;
        }
        formEl.dataset.detachmentSubmitBound = '1';
        formEl.addEventListener('submit', function () {
            formEl.querySelectorAll('select[name^="form-"][name$="-placement_zone"]').forEach(function (select) {
                syncDestForSelect(select);
            });
        }, true);
    }

    function bindInlinePlacementSelect(select) {
        if (select.dataset.detachmentBound === '1') {
            return;
        }
        select.dataset.detachmentBound = '1';
        select.dataset.initialZone = select.value;

        select.addEventListener('change', function () {
            const initialZone = select.dataset.initialZone || '';
            const inline = select.closest('.inline-related, fieldset');
            const notesField = inline
                ? inline.querySelector('textarea[name$="-notes"], input[name$="-notes"]:not([type="hidden"])')
                : null;

            if (select.value !== DETACHMENT || initialZone === DETACHMENT) {
                updateNotesLabel(select, notesField);
                return;
            }

            let destination = notesField ? notesField.value.trim() : '';
            if (!destination) {
                destination = (window.prompt(PROMPT_TEXT) || '').trim();
            }
            if (!destination) {
                select.value = initialZone;
                window.alert('Укажите, куда перемещаем. Перевод на отрыв отменён.');
                return;
            }

            if (notesField) {
                notesField.value = destination;
            }
            updateNotesLabel(select, notesField);
        });

        const inline = select.closest('.inline-related, fieldset');
        const notesField = inline
            ? inline.querySelector('textarea[name$="-notes"], input[name$="-notes"]:not([type="hidden"])')
            : null;
        updateNotesLabel(select, notesField);
    }

    function updateNotesLabel(select, notesField) {
        if (!notesField) {
            return;
        }
        const label = notesField.closest('.form-row, .field-notes');
        if (!label) {
            return;
        }
        const labelEl = label.querySelector('label');
        if (labelEl) {
            labelEl.textContent = select.value === DETACHMENT ? PROMPT_TEXT : 'Примечания:';
        }
    }

    function init() {
        document.querySelectorAll('select[name$="-placement_zone"]').forEach(function (select) {
            if (select.name.indexOf('form-') === 0) {
                bindPlacementSelect(select);
            } else {
                bindInlinePlacementSelect(select);
            }
        });
        bindChangelistSubmit();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
