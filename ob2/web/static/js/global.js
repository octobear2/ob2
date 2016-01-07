$(document).ready(function() {
    $(".js-ob2--log-out-link-form a").click(function(event) {
        event.preventDefault();
        $(this).closest("form.js-ob2--log-out-link-form").submit();
    });
});
