var confirmModal = {
    ar: "تأكيد",
    de: "Bestätigen",
    es: "Confirmar",
    en: "Confirm",
    fr: "Confirmer",
};

var cancelModal = {
    ar: "إلغاء",
    de: "Abbrechen",
    es: "Cancelar",
    en: "Cancel",
    fr: "Annuler",
};

    function addToSelectedId(newIds){
      ids = JSON.parse(
        $("#selectedInstances").attr("data-ids") || "[]"
      );

      ids = [...ids,...newIds.map(String)]
      ids = Array.from(new Set(ids));
      $("#selectedInstances").attr("data-ids",JSON.stringify(ids))
    }
    function selectSelected(viewId){
      ids = JSON.parse(
          $("#selectedInstances").attr("data-ids") || "[]"
        );
      $.each(ids, function (indexInArray, valueOfElement) {
        $(`${viewId} .oh-sticky-table__tbody .list-table-row[value=${valueOfElement}]`).prop("checked",true).change()
      });
      $(`${viewId} .oh-sticky-table__tbody .list-table-row`).change(function (
        e
      ) {
        id = $(this).val()
        ids = JSON.parse(
            $("#selectedInstances").attr("data-ids") || "[]"
          );
        ids = Array.from(new Set(ids));
        let index = ids.indexOf(id);
        if (!ids.includes(id)) {
          ids.push(id);
        } else {
          if (!$(this).is(":checked")) {
            ids.splice(index, 1);
          }
        }
        $("#selectedInstances").attr("data-ids", JSON.stringify(ids));
        }
      );
      reloadSelectedCount($('#count_{{view_id|safe}}'));

    }
    function reloadSelectedCount(targetElement) {
      count = JSON.parse($("#selectedInstances").attr("data-ids") || "[]").length
      id =targetElement.attr("id")
      if (id) {
        id =id.split("count_")[1]
      }
      if (count) {
        targetElement.html(count)
        targetElement.parent().removeClass("d-none");
        $(`#unselect_${id}, #export_${id}, #bulk_udate_${id}`).removeClass("d-none");


      }else{
        targetElement.parent().addClass("d-none")
        $(`#unselect_${id}, #export_${id}, #bulk_udate_${id}`).addClass("d-none")

      }
    }
    function removeId(element){
      id = element.val();
      viewId = element.attr("data-view-id")
      ids = JSON.parse($("#selectedInstances").attr("data-ids") || "[]")
      let elementToRemove = 5;
      if (ids[ids.length - 1] === id) {
          ids.pop();
      }
      ids = JSON.stringify(ids)
      $("#selectedInstances").attr("data-ids", ids);

    }
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === name + "=") {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function addToSelectedId(newIds, storeKey) {

    ids = JSON.parse(
        $(`#${storeKey}`).attr("data-ids") || "[]"
    );

    ids = [...ids, ...newIds.map(String)]
    ids = Array.from(new Set(ids));
    $(`#${storeKey}`).attr("data-ids", JSON.stringify(ids))
}

function attendanceDateChange(selectElement) {
    var selectedDate = selectElement.val()
    let parentForm = selectElement.parents().closest("form")
    var shiftId = parentForm.find("[name=shift_id]").val()

    $.ajax({
        type: "post",
        url: "/attendance/update-date-details",
        data: {
            csrfmiddlewaretoken: getCookie("csrftoken"),
            "attendance_date": selectedDate,
            "shift_id": shiftId
        },
        success: function (response) {
            parentForm.find("[name=minimum_hour]").val(response.minimum_hour)

        }
    });
}

function getAssignedLeave(employeeElement) {
    var employeeId = employeeElement.val()
    $.ajax({
        type: "get",
        url: "/payroll/get-assigned-leaves",
        data: { "employeeId": employeeId },
        dataType: "json",
        success: function (response) {
            let rows = ""
            for (let index = 0; index < response.length; index++) {
                const element = response[index];
                rows = rows + `<tr class="toggle-highlight"><td>${element.leave_type_id__name
                    }</td><td>${element.available_days}</td><td>${element.carryforward_days}</td></tr>`
            }
            $("#availableTableBody").html($(rows))
            let newLeaves = ""
            for (let index = 0; index < response.length; index++) {
                const leave = response[index];
                newLeaves = newLeaves + `<option value="${leave.leave_type_id__id
                    }">${leave.leave_type_id__name}</option>`
            }
            $('#id_leave_type_id').html(newLeaves)
            removeHighlight()
        }
    });
}
function selectSelected(viewId, storeKey = "selectedInstances") {

    ids = JSON.parse(
        $(`#${storeKey}`).attr("data-ids") || "[]"
    );
    $.each(ids, function (indexInArray, valueOfElement) {
        $(`${viewId} .oh-sticky-table__tbody .list-table-row[value=${valueOfElement}]`).prop("checked", true).change()
        $(`${viewId} tbody .list-table-row[value=${valueOfElement}]`).prop("checked", true).change()
    });
    $(`${viewId} .oh-sticky-table__tbody .list-table-row,${viewId} tbody .list-table-row`,).change(function (
        e
    ) {
        id = $(this).val()
        ids = JSON.parse(
            $(`#${storeKey}`).attr("data-ids") || "[]"
        );
        ids = Array.from(new Set(ids));
        let index = ids.indexOf(id);
        if (!ids.includes(id)) {
            ids.push(id);
        } else {
            if (!$(this).is(":checked")) {
                ids.splice(index, 1);
            }
        }
        $(`#${storeKey}`).attr("data-ids", JSON.stringify(ids));
    }
    );
    if (viewId) {
        reloadSelectedCount($(`#count_${viewId}`), storeKey);
    }

}

// Switch General Tab
function switchGeneralTab(e) {
    // DO NOT USE GENERAL TABS TWICE ON A SINGLE PAGE.
    e.preventDefault();
    e.stopPropagation();
    let clickedEl = e.target.closest(".oh-general__tab-link");
    let targetSelector = clickedEl.dataset.target;

    // Remove active class from all the tabs
    $(".oh-general__tab-link").removeClass("oh-general__tab-link--active");
    // Remove active class to the clicked tab
    clickedEl.classList.add("oh-general__tab-link--active");

    // Hide all the general tabs
    $(".oh-general__tab-target").addClass("d-none");
    // Show the tab with the chosen target
    $(`.oh-general__tab-target${targetSelector}`).removeClass("d-none");
}

function toggleReimbursmentType(element) {
    if (element.val() == 'reimbursement') {
        $('#objectCreateModalTarget [name=attachment]').parent().show()
        $('#objectCreateModalTarget [name=attachment]').attr("required", true)
        $('#objectCreateModalTarget [name=leave_type_id]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget [name=cfd_to_encash]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget [name=ad_to_encash]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget [name=amount]').parent().show().attr("required", true)
        $('#objectCreateModalTarget #availableTable').hide().attr("required", false)
        $('#objectCreateModalTarget [name=bonus_to_encash]').parent().hide().attr("required", false)

    } else if (element.val() == 'leave_encashment') {
        $('#objectCreateModalTarget [name=attachment]').parent().hide()
        $('#objectCreateModalTarget [name=attachment]').attr("required", false)
        $('#objectCreateModalTarget [name=leave_type_id]').parent().show().attr("required", true)
        $('#objectCreateModalTarget [name=cfd_to_encash]').parent().show().attr("required", true)
        $('#objectCreateModalTarget [name=ad_to_encash]').parent().show().attr("required", true)
        $('#objectCreateModalTarget [name=amount]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget #availableTable').show().attr("required", true)
        $('#objectCreateModalTarget [name=bonus_to_encash]').parent().hide().attr("required", false)

    } else if (element.val() == 'bonus_encashment') {
        $('#objectCreateModalTarget [name=attachment]').parent().hide()
        $('#objectCreateModalTarget [name=attachment]').attr("required", false)
        $('#objectCreateModalTarget [name=leave_type_id]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget [name=cfd_to_encash]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget [name=ad_to_encash]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget [name=amount]').parent().hide().attr("required", false)
        $('#objectCreateModalTarget #availableTable').hide().attr("required", false)
        $('#objectCreateModalTarget [name=bonus_to_encash]').parent().show().attr("required", true)


    }
}

function reloadSelectedCount(targetElement, storeKey = "selectedInstances") {
    var count = JSON.parse($(`#${storeKey}`).attr("data-ids") || "[]").length
    id = targetElement.attr("id")
    if (id) {
        id = id.split("count_")[1]
    }
    if (count) {
        targetElement.html(count)
        targetElement.parent().removeClass("d-none");
        $(`#unselect_${id}, #export_${id}, #bulk_udate_${id}`).removeClass("d-none");


    } else {
        targetElement.parent().addClass("d-none")
        $(`#unselect_${id}, #export_${id}, #bulk_udate_${id}`).addClass("d-none")

    }
}



function removeHighlight() {
    setTimeout(function () {
        $(".toggle-highlight").removeClass("toggle-highlight")
    }, 200);
}

function removeId(element, storeKey = "selectedInstances") {
    id = element.val();
    viewId = element.attr("data-view-id")
    ids = JSON.parse($(`#${storeKey}`).attr("data-ids") || "[]")
    let elementToRemove = 5;
    if (ids[ids.length - 1] === id) {
        ids.pop();
    }
    ids = JSON.stringify(ids)
    $(`#${storeKey}`).attr("data-ids", ids);

}

function updateStagesAndContainers(response, recruitmentId) {
    // 1. Mettre à jour les conteneurs d'étapes affectés
    if (response.stages_html) {
        Object.keys(response.stages_html).forEach(function(stageId) {
            $(`#pipelineStageContainer${stageId}`).html(response.stages_html[stageId]);
            
            // Mettre à jour le compteur
            if (response.stage_counts && response.stage_counts[stageId]) {
                $(`#stageCount${stageId}`).text(response.stage_counts[stageId]);
                $(`#stageCount${stageId}`).attr("title", `${response.stage_counts[stageId]} candidates`);
            }
        });
    }

    // 2. Mettre à jour l'ordre des étapes si fourni
    if (response.stages_order) {
        const stagesContainer = $(`#stageContainer${recruitmentId}`);
        const stages = stagesContainer.children('.stage').get();
        
        // Trier les étapes selon l'ordre reçu
        stages.sort(function(a, b) {
            const aOrder = response.stages_order[$(a).data('stage-id')] || 0;
            const bOrder = response.stages_order[$(b).data('stage-id')] || 0;
            return aOrder - bOrder;
        });

        // Réappliquer les étapes dans le bon ordre
        stages.forEach(function(stage) {
            stagesContainer.append(stage);
        });
    }

    // 3. Réinitialiser le drag & drop
    if (typeof initializeDragDrop === 'function') {
        initializeDragDrop();
    }
}

function bulkStageUpdate(canIds, stageId, preStageId) {
    $.ajax({
        type: "POST",
        url: "/recruitment/candidate-stage-change?bulk=True",
        data: {
            csrfmiddlewaretoken: getCookie("csrftoken"), 
            canIds: JSON.stringify(canIds),
            stageId: stageId,
        },
        success: function (response, textStatus, jqXHR) {
            if (jqXHR.status === 200) {
                // Afficher le message de succès si présent
                if (response.message) {
                    Swal.fire({
                        title: response.message,
                        text: response.vacancy ? `Total vacancy is ${response.vacancy}` : '',
                        icon: 'success',
                        confirmButtonText: 'Ok',
                    }).then(() => {
                        // Recharger la page après avoir cliqué sur Ok
                        window.location.reload();
                    });
                } else {
                    // Recharger directement si pas de message
                    window.location.reload(); 
                }
            }
        },
        error: function(xhr, status, error) {
            Swal.fire({
                title: 'Erreur',
                text: 'Une erreur est survenue lors de la mise à jour',
                icon: 'error',
                confirmButtonText: 'Ok'
            }); 
        }
    });
}

// Mise à jour de la fonction updateCandStage
function updateCandStage(canIds, stageId, preStageId) {
    $.ajax({
        type: "POST",
        url: "/recruitment/candidate-stage-change?bulk=false",
        data: {
            csrfmiddlewaretoken: getCookie("csrftoken"),
            canIds: canIds,
            stageId: stageId,
        },
        success: function (response, textStatus, jqXHR) {
            if (jqXHR.status === 200) {
                const activeTab = document.querySelector('.oh-tabs__tab--active');
                const recruitmentId = activeTab.getAttribute('data-target').split('_').pop();

                // Utiliser la fonction commune
                updateStagesAndContainers(response, recruitmentId);

                if (response.message) {
                    Swal.fire({
                        title: response.message,
                        text: response.vacancy ? `Total vacancy is ${response.vacancy}` : '',
                        icon: 'success',
                        confirmButtonText: 'Ok',
                    });
                }
            }
        },
        error: function(xhr, status, error) {
            Swal.fire({
                title: 'Erreur',
                text: 'Une erreur est survenue lors de la mise à jour',
                icon: 'error',
                confirmButtonText: 'Ok'
            });
        }
    });
}

function updateStageContainers(response, preStageId, stageId) {
    if (response.stages_html) {
        if (response.stages_html[preStageId]) {
            $(`#pipelineStageContainer${preStageId}`).html(response.stages_html[preStageId]);
        }
        if (response.stages_html[stageId]) {
            $(`#pipelineStageContainer${stageId}`).html(response.stages_html[stageId]);
        }
    }
    
    if (response.stage_counts) {
        if (response.stage_counts[preStageId]) {
            $(`#stageCount${preStageId}`).text(response.stage_counts[preStageId]);
        }
        if (response.stage_counts[stageId]) {
            $(`#stageCount${stageId}`).text(response.stage_counts[stageId]);
        }
    }

    // Recharger les conteneurs de stage mis à jour
    $(`#stageLoad${preStageId}`).click();
    $(`#stageLoad${stageId}`).click();
}

function checkSequence(element) {
    var preStageId = $(element).data("stage_id")
    var canIds = $(element).data("cand_id")
    var stageOrderJson = $(element).attr("data-stage_order")
    var stageId = $(element).val()

    var parsedStageOrder = JSON.parse(stageOrderJson);

    var stage = parsedStageOrder.find(stage => stage.id == stageId);
    var preStage = parsedStageOrder.find(stage => stage.id == preStageId);
    var stageOrder = parsedStageOrder.map(stage => stage.id);

    if (stageOrder.indexOf(parseInt(stageId)) != stageOrder.indexOf(parseInt(preStageId)) + 1 && stage.type != "cancelled") {
        Swal.fire({
            title: "Confirm",
            text: `Are you sure to change the candidate from ${preStage.stage} stage to ${stage.stage} stage`,
            icon: 'info',
            showCancelButton: true,
            confirmButtonColor: "#008000",
            cancelButtonColor: "#d33",
            confirmButtonText: "Confirm",
        }).then(function (result) {
            if (result.isConfirmed) {
                updateCandStage(canIds, stageId, preStageId)
            }
        });
    }
    else {
        updateCandStage(canIds, stageId, preStageId)
    }
}

function reloadMessage(e) {
    $('#reloadMessagesButton').click();
}

function ajaxWithResponseHandler(event) {
    $(event.target).each(function () {
        $.each(this.attributes, function () {
            if (this.specified && this.name === 'hx-on-htmx-after-request') {
                eval(this.value);
            }
        });
    });
}

var originalConfirm = window.confirm;
// Override the default confirm function with SweetAlert
window.confirm = function (message) {
    var event = window.event || {};
    event.preventDefault();
    var languageCode = $("#main-section-data").attr("data-lang") || "en";
    var confirm = confirmModal[languageCode];
    var cancel = cancelModal[languageCode];

    $("#confirmModalBody").html(message);
    var submit = false;

    Swal.fire({
        text: message,
        icon: "question",
        showCancelButton: true,
        confirmButtonColor: "#008000",
        cancelButtonColor: "#d33",
        confirmButtonText: confirm,
        cancelButtonText: cancel,
    }).then((result) => {
        if (result.isConfirmed) {
            var path = event.target["htmx-internal-data"]?.path;
            var verb = event.target["htmx-internal-data"]?.verb;
            var hxTarget = $(event.target).attr("hx-target");
            var hxVals = $(event.target).attr("hx-vals") ? JSON.parse($(event.target).attr("hx-vals")) : {};
            var hxSwap = $(event.target).attr("hx-swap");
            $(event.target).each(function () {
                $.each(this.attributes, function () {
                    if (this.specified && this.name === 'hx-on-htmx-before-request') {
                        eval(this.value);

                    }
                });
            });
            if (event.target.tagName.toLowerCase() === "form") {
                if (path && verb) {
                    if (verb === "post") {
                        htmx.ajax("POST", path, { target: hxTarget, swap: hxSwap, values: hxVals })
                            .then(response => {
                                ajaxWithResponseHandler(event);
                            });
                    } else {
                        htmx.ajax("GET", path, { target: hxTarget, swap: hxSwap, values: hxVals }).then(response => {
                            ajaxWithResponseHandler(event);
                        });
                    }
                } else {
                    event.target.submit();
                }
            } else if (event.target.tagName.toLowerCase() === "a") {
                if (event.target.href) {
                    window.location.href = event.target.href;
                } else {
                    if (verb === "post") {
                        htmx.ajax("POST", path, { target: hxTarget, swap: hxSwap, values: hxVals }).then(response => {
                            ajaxWithResponseHandler(event);
                        });
                    } else {
                        htmx.ajax("GET", path, { target: hxTarget, swap: hxSwap, values: hxVals }).then(response => {
                            ajaxWithResponseHandler(event);
                        });
                    }
                }
            } else {
                if (verb === "post") {
                    htmx.ajax("POST", path, { target: hxTarget, swap: hxSwap, values: hxVals }).then(response => {
                        ajaxWithResponseHandler(event);
                    });
                } else {
                    htmx.ajax("GET", path, { target: hxTarget, swap: hxSwap, values: hxVals }).then(response => {
                        ajaxWithResponseHandler(event);
                    });
                }
            }
        }
    });
};

setTimeout(() => { $("[name='search']").focus() }, 100);

$("#close").attr(
    "class",
    "oh-activity-sidebar__header-icon me-2 oh-activity-sidebar__close md hydrated"
);

$('body').on('click', '.select2-search__field', function (e) {
    //When click on Select2 fields in filter form,Auto close issue
    e.stopPropagation();
});

var nav = $("section.oh-wrapper.oh-main__topbar");
nav.after(
    $(
        `
  <div id="filterTagContainerSectionNav" class="oh-titlebar-container__filters mb-2 mt-0 oh-wrapper"></div>
  `
    )
);

$(document).on("htmx:beforeRequest", function (event, data) {
    var response = event.detail.xhr.response;
    var target = $(event.detail.elt.getAttribute("hx-target"));
    var avoid_target = ["BiometricDeviceTestFormTarget", "reloadMessages", "infinite"];
    if (!target.closest("form").length && avoid_target.indexOf(target.attr("id")) === -1) {
        target.html(`<div class="animated-background"></div>`);
    }
});

$(document).on('keydown', function (event) {
    // Check if the cursor is not focused on an input field
    var isInputFocused = $(document.activeElement).is('input, textarea, select');

    if (event.keyCode === 27) {
        // Key code 27 for Esc in keypad
        $('.oh-modal--show').removeClass('oh-modal--show');
        $('.oh-activity-sidebar--show').removeClass('oh-activity-sidebar--show')
    }

    if (event.keyCode === 46) {
        // Key code 46 for delete in keypad
        // If there have any objectDetailsModal with oh-modal--show
        // take delete button inside that else take the delete button from navbar Actions
        if (!isInputFocused) {
            var $modal = $('.oh-modal--show');
            var $deleteButton = $modal.length ? $modal.find('[data-action="delete"]') : $('.oh-dropdown').find('[data-action="delete"]');
            if ($deleteButton.length) {
                $deleteButton.click();
                $deleteButton[0].click();
            }
        }
    }
    else if (event.keyCode === 107) { // Key code for the + key on the numeric keypad
        if (!isInputFocused) {
            // Click the create option from navbar of current page
            $('[data-action="create"]').click();
        }
    }
    else if (event.keyCode === 39) { // Key code for the right arrow key
        if (!isInputFocused) {
            var $modal = $('.oh-modal--show');
            var $nextButton = $modal.length ? $modal.find('[data-action="next"]') : $('[data-action="next"]');  // Click on the next button in detail view modal
            if ($nextButton.length) {
                $nextButton[0].click()
            }
        }
    }
    else if (event.keyCode === 37) { // Key code for the left arrow key
        if (!isInputFocused) {
            // Click on the previous button in detail view modal
            var $modal = $('.oh-modal--show');
            var $previousButton = $modal.length ? $modal.find('[data-action="previous"]') : $('[data-action="previous"]');
            if ($previousButton.length) {
                $previousButton[0].click();

            }
        }
    }
});
function handleDownloadAndRefresh(event, url) {
    // Use in import_popup.html file
    event.preventDefault();

    // Create a temporary hidden iframe to trigger the download
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);

    // Refresh the page after a short delay
    setTimeout(function () {
        document.body.removeChild(iframe);  // Clean up the iframe
        window.location.reload();  // Refresh the page
    }, 500);  // Adjust the delay as needed
}

function updateUserPanelCount(e) {
    var count = $(e).closest('.oh-sticky-table__tr').find('.oh-user-panel').length;
    setTimeout(() => {
        var $permissionCountSpan = $(e).closest('.oh-permission-table--toggle').parent().find('.oh-permission-count');
        var currentText = $permissionCountSpan.text();

        var firstSpaceIndex = currentText.indexOf(' ');
        var textAfterNumber = currentText.slice(firstSpaceIndex + 1);
        var newText = count + ' ' + textAfterNumber;

        $permissionCountSpan.text(newText);

    }, 100);
}

function sendAcknowledgement() {
    $.ajax({
        url: '/recruitment/send-acknowledgement',
        method: 'POST',
        data: formData,
        success: function(response) {
            if (response.redirectUrl) {
                // Ouvre l'auth Google dans une nouvelle fenêtre
                window.open(response.redirectUrl, 'googleAuth', 'width=600,height=600');
            } else {
                // Affiche le message de succès
                swal.fire('Succès', 'Message envoyé !', 'success');
            }
        }
    });
}



// ============================================================================
// FONCTIONS SUMMERNOTE (pour l'éditeur de texte)
// ============================================================================
function preloadData(item, candId, preloadedData, callback) {
    $.ajax({
        type: "get",
        url: `/recruitment/get-template-hint/`,
        data: { "candidate_id": candId, 'word': item },
        success: function(response) {
            preloadedData[item] = response.body;
            callback();
            $('.note-hint-popover').hide()
        }
    });
}

function initializeSummernote(candId, searchWords) {
    var preloadedData = {};
    var searchWords = searchWords;
    var mentions = Object.keys(searchWords);
    $("[name='body']").summernote({
        hint: {
            mentions: mentions,
            match: /\B\{(\w*)$/,
            search: function(keyword, callback) {
                var pattern = new RegExp(keyword, "i");
                callback($.grep(this.mentions, function(item) {
                    return pattern.test(item);
                }));
            },
            content: function(item) {
                var word = searchWords[item];
                if (preloadedData[word]) {
                    $("[name='body']").summernote('insertText', preloadedData[word]);
                    $('.note-hint-popover').hide();
                } else {
                    preloadData(word, candId, preloadedData, function() {
                        $("[name='body']").summernote('insertText', preloadedData[word]);
                    });
                }
            }
        }
    });
}

// ============================================================================
// FONCTIONS DE VALIDATION DE FICHIERS
// ============================================================================
function validateFile(element, fileTarget, reload = false) {
    var fileInput = document.getElementById(fileTarget);
    var filePath = fileInput.value;
    var allowedExtensions = /(\.xlsx|\.csv)$/i;

    if (!allowedExtensions.exec(filePath)) {
        Swal.fire({
            icon: 'error',
            title: '{% trans "Invalid File" %}',
            text: '{% trans "Please upload a valid XLSX file." %}',
            customClass: {
                popup: 'file-xlsx-validation',
            },
        })
        .then((result) => {
            if (result.isConfirmed && reload) {
                $(".oh-modal--show").removeClass("oh-modal--show");
                window.location.reload()
            }
        });
        fileInput.value = '';
        return false;
    }
    $(this).closest("form").submit();
}

// ============================================================================
// FONCTIONS DE GESTION DES FILTRES
// ============================================================================
function filterCountUpdate(formId) {
    var formData = $("#" + formId).serialize();
    var count = 0;
    formData.split("&").forEach(function (field) {
        var parts = field.split("=");
        var value = parts[1];
        if (parts[0] !== "view" && parts[0] !== "filter_applied") {
            if (value && value !== "unknown") {
                count++;
            }
        }
    });
    $("#filterCount").empty();
    if (count > 0) {
        $("#filterCount").text(`(${count})`);
    }
}

// ============================================================================
// FONCTIONS DE GESTION DES TABLEAUX (highlight des lignes)
// ============================================================================
function highlightRow(checkbox) {
    checkbox.closest(".oh-sticky-table__tr").removeClass("highlight-selected");
    checkbox.closest("tr").removeClass("highlight-selected");
    if (checkbox.is(":checked")) {
        checkbox.closest(".oh-sticky-table__tr").addClass("highlight-selected");
        checkbox.closest("tr").addClass("highlight-selected");
    }
}

function toggleHighlight(ids) {
    $.each(ids, function (indexInArray, id) {
        setTimeout(() => {
            $(`#${id}`)
                .closest(".oh-sticky-table__tr")
                .removeClass("highlight-selected");
            if ($(`#${id}`).is(":checked")) {
                $(`#${id}`)
                    .closest(".oh-sticky-table__tr")
                    .addClass("highlight-selected");
            }
        }, 1);
    });
}

// ============================================================================
// FONCTIONS DE GESTION DES GRAPHIQUES
// ============================================================================
function emptyChart(chart, args, options) {
    flag = false;
    for (let i = 0; i < chart.data.datasets.length; i++) {
        flag = flag + chart.data.datasets[i].data.some(Boolean);
    }
    if (!flag) {
        const { ctx, canvas } = chart;
        chart.clear();
        const parent = canvas.parentElement;

        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
        const x = canvas.width / 2;
        const y = (canvas.height - 70) / 2;
        var noDataImage = new Image();
        noDataImage.src = chart.data.emptyImageSrc
            ? chart.data.emptyImageSrc
            : "{% static '/images/ui/joiningchart.png' %}";

        message = chart.data.message
            ? chart.data.message
            : emptyMessages[languageCode];

        noDataImage.onload = () => {
            ctx.drawImage(noDataImage, x - 35, y, 70, 70);
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "hsl(0,0%,45%)";
            ctx.font = "16px Poppins";
            ctx.fillText(message, x, y + 70 + 30);
        };
    }
}

// ============================================================================
// GESTION DES LANGUES POUR LES MESSAGES D'ERREUR
// ============================================================================
var message;
var languageCode = "en";
var emptyMessages = {
    ar: "...لم يتم العثور على بيانات",
    de: "Keine Daten gefunden...",
    es: "No se encontraron datos...",
    en: "No data Found...",
    fr: "Aucune donnée trouvée...",
};

$.ajax({
    type: "GET",
    url: "/employee/get-language-code/",
    success: function (response) {
        languageCode = response.language_code;
        message = emptyMessages[languageCode];
    },
});


