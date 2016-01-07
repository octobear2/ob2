$(document).ready(function() {

    var group_min = group_limits[0];
    var group_max = group_limits[1];

    function get_last_row() {
        return [$(".js-ob2__div_student:last")];
    }

    var pristine_row = [];
    $.each(get_last_row(), function(_, component) {
        pristine_row.push(component.clone());
    });

    function add_row() {
        var container = $(".js-ob2__rows");
        $.each(pristine_row, function(_, component) {
            var component_copy = component.clone();
            component_copy.find(".mdl-js-textfield").each(function(_, textfield) {
                delete textfield.dataset["upgraded"];
                textfield.classList.remove("is-upgraded");
            });
            container.append(component_copy);
        });
        /* http://www.getmdl.io/started/index.html#dynamic */
        componentHandler.upgradeDom("MaterialTextfield", "mdl-js-textfield");
    }

    var last_row = get_last_row();
    function push_new_row() {
        if ($(this).val().length > 0 && $(".js-ob2__div_student").length < group_max - 1) {
            add_row();
            $.each(last_row, function(_, component) {
                component.find("input[type=text]").off("input");
            });
            last_row = get_last_row();
            $.each(last_row, function(_, component) {
                component.find("input[type=text]").on("input", push_new_row);
            });
        }
    }

    $.each(last_row, function(_, component) {
        component.find("input[type=text]").on("input", push_new_row);
    });

});
