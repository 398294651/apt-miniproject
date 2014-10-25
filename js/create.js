$('input[name=filename]').change(function() {
    $('input[name=image_id]').val($(this).val());
});
