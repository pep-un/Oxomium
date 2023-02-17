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
