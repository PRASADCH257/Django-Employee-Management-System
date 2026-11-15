document.addEventListener('DOMContentLoaded', function () {
    const photoInput = document.getElementById('id_photo');
    const preview = document.getElementById('profile-image-preview');
    const placeholder = document.getElementById('profile-image-placeholder');
    let previewUrl = null;

    if (!photoInput || !preview) {
        return;
    }

    photoInput.addEventListener('change', function () {
        const file = photoInput.files && photoInput.files[0];
        if (!file || (file.type && !file.type.startsWith('image/'))) {
            return;
        }

        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
        previewUrl = URL.createObjectURL(file);
        preview.src = previewUrl;
        preview.hidden = false;
        if (placeholder) {
            placeholder.hidden = true;
        }
    });

    window.addEventListener('beforeunload', function () {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
    });
});
