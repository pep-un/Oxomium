if (document.getElementById('accordion')){
    // Dirty fix for Date form
    // https://github.com/zostera/django-bootstrap5/issues/445
    // TODO: contribute upstream to django-bootstrap
    document.getElementById('id_control_date').type = 'Date'
    document.getElementById('id_implement_start_date').type = 'Date'
    document.getElementById('id_implement_end_date').type = 'Date'
    document.getElementById('id_plan_start_date').type = 'Date'
    document.getElementById('id_plan_end_date').type = 'Date'

    // Open the good accordion at page load
    if (document.getElementById('id_status').value == '1') {
        document.getElementById('id_status_comment').parentNode.classList.add("d-none");
        document.getElementById('buttonAnalyse').classList.remove("collapsed");
        document.getElementById('collapseAnalyse').classList.add("show");
    } else if (document.getElementById('id_status').value == '2') {
        document.getElementById('id_status_comment').parentNode.classList.add("d-none");
        document.getElementById('buttonPlan').classList.remove("collapsed");
        document.getElementById('collapsePlan').classList.add("show");
    } else if (document.getElementById('id_status').value == '3') {
        document.getElementById('id_status_comment').parentNode.classList.add("d-none");
        document.getElementById('buttonImplement').classList.remove("collapsed");
        document.getElementById('collapseImplement').classList.add("show");
    } else if (document.getElementById('id_status').value == '4') {
        document.getElementById('id_status_comment').parentNode.classList.add("d-none");
        document.getElementById('buttonControl').classList.remove("collapsed");
        document.getElementById('collapseControl').classList.add("show");
    }

    // Display the field id_status_comment for MISC status
    document.getElementById('id_status').onchange = function(){
        if (document.getElementById('id_status').value > '5') {
            document.getElementById('id_status_comment').parentNode.classList.remove("d-none");
            document.getElementById('id_status_comment').required = true;
        } else {
            document.getElementById('id_status_comment').parentNode.classList.add("d-none");
            document.getElementById('id_status_comment').required = false;
        }
    };
}

if (document.getElementById('id_start_date')){
    // Dirty fix for Date form
    // https://github.com/zostera/django-bootstrap5/issues/445
    // TODO: contribute upstream to django-bootstrap
    document.getElementById('id_start_date').type = 'Date'
    document.getElementById('id_end_date').type = 'Date'
    document.getElementById('id_report_date').type = 'Date'
}


document.querySelectorAll('.js-copy-sha256').forEach((button) => {
    button.addEventListener('click', async () => {
        const value = button.dataset.copyValue;
        if (!value) {
            return;
        }

        const originalTitle = button.getAttribute('title') || 'Copy SHA-256';
        try {
            await navigator.clipboard.writeText(value);
            button.setAttribute('title', 'Copied');
            button.classList.remove('btn-outline-secondary');
            button.classList.add('btn-outline-success');
            window.setTimeout(() => {
                button.setAttribute('title', originalTitle);
                button.classList.remove('btn-outline-success');
                button.classList.add('btn-outline-secondary');
            }, 1500);
        } catch (error) {
            button.setAttribute('title', 'Copy failed');
            button.classList.remove('btn-outline-secondary');
            button.classList.add('btn-outline-danger');
            window.setTimeout(() => {
                button.setAttribute('title', originalTitle);
                button.classList.remove('btn-outline-danger');
                button.classList.add('btn-outline-secondary');
            }, 1500);
        }
    });
});



const attachmentInputs = Array.from(document.querySelectorAll('.js-attachment-input'));

function attachmentFileKey(file) {
    return [file.name, file.size, file.type, file.lastModified].join('|');
}

function screenshotFilename(file) {
    const date = new Date();
    const pad = (value) => String(value).padStart(2, '0');
    const extension = file.type && file.type.includes('/')
        ? file.type.split('/')[1].replace('jpeg', 'jpg')
        : 'png';
    return [
        'Screenshot',
        date.getFullYear(),
        pad(date.getMonth() + 1),
        pad(date.getDate()),
        pad(date.getHours()) + pad(date.getMinutes()) + pad(date.getSeconds()),
    ].join('-') + '.' + extension;
}

function isTextEditingTarget(target) {
    if (!target) {
        return false;
    }
    const tagName = target.tagName ? target.tagName.toLowerCase() : '';
    return target.isContentEditable || tagName === 'textarea' ||
        (tagName === 'input' && !['file', 'button', 'submit'].includes(target.type));
}

attachmentInputs.forEach((input) => {
    const panel = input.closest('.js-attachment-panel');
    const dropzone = panel ? panel.querySelector('.js-attachment-dropzone') : null;
    const pending = panel ? panel.querySelector('.js-attachment-pending') : null;
    const transfer = new DataTransfer();

    if (!dropzone || !pending) {
        return;
    }

    const renderPending = () => {
        pending.replaceChildren();
        const files = Array.from(transfer.files);
        pending.classList.toggle('d-none', files.length === 0);

        files.forEach((file, index) => {
            const row = document.createElement('div');
            row.className = 'd-flex align-items-center justify-content-between gap-3 py-1';

            const label = document.createElement('span');
            label.className = 'small text-truncate';
            label.innerHTML = '<i class="bi bi-file-earmark-plus me-1" aria-hidden="true"></i>';
            label.append(document.createTextNode(file.name));

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'btn btn-sm btn-outline-secondary flex-shrink-0';
            remove.setAttribute('aria-label', 'Remove pending file ' + file.name);
            remove.setAttribute('title', 'Remove pending file');
            remove.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            remove.addEventListener('click', () => {
                const next = new DataTransfer();
                Array.from(transfer.files).forEach((current, currentIndex) => {
                    if (currentIndex !== index) {
                        next.items.add(current);
                    }
                });
                transfer.items.clear();
                Array.from(next.files).forEach((current) => transfer.items.add(current));
                input.files = transfer.files;
                renderPending();
            });

            row.append(label, remove);
            pending.append(row);
        });
    };

    const addFiles = (files) => {
        const known = new Set(Array.from(transfer.files).map(attachmentFileKey));
        Array.from(files).forEach((file) => {
            const key = attachmentFileKey(file);
            if (!known.has(key)) {
                transfer.items.add(file);
                known.add(key);
            }
        });
        input.files = transfer.files;
        renderPending();
    };

    input.addEventListener('change', () => {
        addFiles(Array.from(input.files));
    });

    const hasDraggedFiles = (event) => (
        event.dataTransfer &&
        Array.from(event.dataTransfer.types || []).includes('Files')
    );

    let dragFocusActive = false;

    document.addEventListener('dragenter', (event) => {
        if (!hasDraggedFiles(event)) {
            return;
        }

        dropzone.classList.add('is-dragging');
        if (!dragFocusActive) {
            dragFocusActive = true;
            dropzone.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest',
            });
        }
    });

    document.addEventListener('dragover', (event) => {
        if (hasDraggedFiles(event)) {
            event.preventDefault();
            dropzone.classList.add('is-dragging');
        }
    });

    document.addEventListener('dragleave', (event) => {
        if (!event.relatedTarget) {
            dropzone.classList.remove('is-dragging');
            dragFocusActive = false;
        }
    });

    document.addEventListener('drop', (event) => {
        if (hasDraggedFiles(event)) {
            event.preventDefault();
        }
        dropzone.classList.remove('is-dragging');
        dragFocusActive = false;
    });

    panel.addEventListener('dragover', (event) => {
        if (hasDraggedFiles(event)) {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
        }
    });

    panel.addEventListener('drop', (event) => {
        if (!hasDraggedFiles(event)) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove('is-dragging');
        dragFocusActive = false;
        addFiles(event.dataTransfer.files);
    });

    input._addAttachmentFiles = addFiles;
});

document.addEventListener('paste', (event) => {
    if (isTextEditingTarget(event.target)) {
        return;
    }

    const pastedFiles = Array.from(event.clipboardData?.files || []);
    if (!pastedFiles.length) {
        return;
    }

    const input = attachmentInputs.find((candidate) => candidate.offsetParent !== null);
    if (!input || typeof input._addAttachmentFiles !== 'function') {
        return;
    }

    const normalized = pastedFiles.map((file) => {
        if (!file.type.startsWith('image/')) {
            return file;
        }
        try {
            return new File(
                [file],
                screenshotFilename(file),
                {type: file.type, lastModified: Date.now()},
            );
        } catch (error) {
            return file;
        }
    });

    event.preventDefault();
    input._addAttachmentFiles(normalized);
});
