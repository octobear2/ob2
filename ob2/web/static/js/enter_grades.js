$(document).ready(function() {
    var validation_data = enter_grades_validation_data;
    var min_score = null;
    var max_score = null;

    $("#f_assignment").on("input", function(event) {
        var value = event.target.value;
        var assignment_names = validation_data["assignment_names"];
        if (value === "" || assignment_names.indexOf(value) !== -1) {
            event.target.setCustomValidity("");
            min_score = validation_data["min_scores"][value];
            max_score = validation_data["max_scores"][value];
            $(".js-ob2__l_score").text("Range: " + min_score + " to " + max_score);
            $(".js-ob2__f_score").trigger("input");
        } else {
            event.target.setCustomValidity("Choose from: " + assignment_names.join(", "));
        }
    });

    function validate_score(event) {
        var value = event.target.value;
        if (value === "") {
            event.target.setCustomValidity("");
        } else if (/^[-+]?[0-9]*\.?[0-9]+$/.test(value) !== true) {
            event.target.setCustomValidity("Invalid score");
        } else if (min_score === null || max_score === null) {
            event.target.setCustomValidity("");
        } else {
            var float_value = parseFloat(value);
            if (min_score <= float_value && float_value <= max_score) {
                event.target.setCustomValidity("");
            } else {
                event.target.setCustomValidity("Range: " + min_score + " to " + max_score);
            }
        }
        /* Dirty dirty hack */
        event.target.parentElement.MaterialTextfield.updateClasses_();
    }

    function validate_student(event) {
        var value = event.target.value;
        var jq_target = $(event.target);
        var message;
        if (value == "") {
            message = "";
        } else if (validation_data["ambiguous_identifiers"].indexOf(value) !== -1) {
            message = "Ambiguous (multiple matches)";
        } else if (validation_data["valid_identifiers"].indexOf(value) !== -1) {
            message = "";
        } else {
            message = "No such student found";
        }
        event.target.setCustomValidity(message);
        jq_target.siblings(".mdl-textfield__error").text(message);
    }

    $(".js-ob2__f_score").on("input", validate_score);
    $(".js-ob2__f_student").on("input", validate_student);

    function get_last_row() {
        return [$(".js-ob2__div_student:last"),
                $(".js-ob2__div_score:last"),
                $(".js-ob2__div_slipunits:last")];
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
            component_copy.find(".js-ob2__f_score").on("input", validate_score);
            component_copy.find(".js-ob2__f_student").on("input", validate_student);
            if (min_score != null && max_score != null) {
                component_copy.find(".js-ob2__l_score").text(
                        "Range: " + min_score + " to " + max_score);
            }
            container.append(component_copy);
        });
        /* http://www.getmdl.io/started/index.html#dynamic */
        componentHandler.upgradeDom("MaterialTextfield", "mdl-js-textfield");
    }

    var last_row = get_last_row();
    function push_new_row() {
        if ($(this).val().length > 0) {
            add_row();
            $.each(last_row, function(_, component) {
                component.find("input[type=text]").off("input", push_new_row);
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
