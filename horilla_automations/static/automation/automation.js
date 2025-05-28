// horilla_automations/static/automation/automation.js - Version corrigée AVEC conditions dynamiques
function getToMail(element) {
  model = element.val();
  $.ajax({
    type: "get",
    url: "/get-to-mail-field",
    data: {
      model: model,
    },
    success: function (response) {
      $(".dynamic-condition-row").remove();
      select = $("#id_mail_to");
      select.html("");
      detailSelect = $("#id_mail_details");
      detailSelect.html("");
      mailTo = response.choices;
      mailDetail = response.mail_details_choice;

      for (let option = 0; option < mailTo.length; option++) {
        const element = mailTo[option];
        var selected = option === 0;
        var newOption = new Option(element[1], element[0], selected, selected);
        select.append(newOption);
      }
      for (let option = 0; option < mailDetail.length; option++) {
        const element = mailDetail[option];
        var selected = option === 0;
        var newOption = new Option(element[1], element[0], selected, selected);
        detailSelect.append(newOption);
      }
      select.trigger("change");
      detailSelect.trigger("change");

      table = $("#multipleConditionTable");
      $("#multipleConditionTable select").select2("destroy");

      totalRows = "C" + (table.find(".dynamic-condition-row").length + 1);

      fieldsChoices = [];
      $.each(response.serialized_form, function (indexInArray, valueOfElement) {
        fieldsChoices.push([valueOfElement["name"], valueOfElement["label"]]);
      });
      
      selectField = populateSelect(fieldsChoices, response);
      tr = `
      <tr class="dynamic-condition-row">
        <td class="sn">${totalRows}</td>
        <td id="conditionalField"></td>
        <td>
        <select name="automation_multiple_condition" onchange="addSelectedAttr(event)" class="w-100">
          <option value="==">==</option>
          <option value="!=">!=</option>
        </select>
        </td>
        <td class="condition-value-th"></td>
        <td>
        <select name="automation_multiple_condition" onchange="addSelectedAttr(event)" class="w-100">
            <option value="and">And</option>
            <option value="or">Or</option>
        </select>
        </td>
        <td>
        <div class="oh-btn-group">
          <button
           class="oh-btn oh-btn oh-btn--light p-2 w-50"
           onclick="
            event.preventDefault();
            var clonedElement = $(this).closest('tr').clone();
            totalRows ='C' +( $(this).closest('table').find('.dynamic-condition-row').length + 1);
            clonedElement.find('.sn').html(totalRows)
            clonedElement.find('select').parent().find('span').remove()
            clonedElement.find('select').attr('class','w-100')

            $(this).closest('tr').parent().append(clonedElement)
            $('#multipleConditionTable').find('select').select2()
           "
          >
            <ion-icon name="copy-outline"></ion-icon>
          </button>
          <button
           class="oh-btn oh-btn oh-btn--light p-2 w-50"
           onclick="
            event.preventDefault();
            $(this).closest('tr').remove();
           "
          >
            <ion-icon name="trash-outline"></ion-icon>
          </button>
        </div>
        </td>
      </tr>
    `;
      table.find("tr:last").after(tr);
      $("#conditionalField").append(selectField);
      $("#multipleConditionTable select").select2();
      selectField.trigger("change");
      selectField.attr("name", "automation_multiple_condition");
    },
  });
}

function getHtml() {
  var htmlCode = `
    <form id="multipleConditionForm">
      <table id="multipleConditionTable">
        <tr>
          <th>Code</th>
          <th>Field</th>
          <th>Condition</th>
          <th>Value</th>
          <th>Logic</th>
          <th>
          Action
          <span title="Reload" onclick="$('[name=model]').change()">
            <ion-icon name="refresh-circle"></ion-icon>
          </span>
          </th>
        </tr>
      </table>
    </form>
    <script>
    $("#multipleConditionTable").closest("[contenteditable=true]").removeAttr("contenteditable");
    </script>
  `;
  return $(htmlCode);
}

function populateSelect(data, response) {
  // Version sécurisée sans échappement JSON problématique
  const selectElement = $(
    '<select class="w-100" onchange="updateValue($(this));addSelectedAttr(event)"></select>'
  );
  
  // Stocker les données directement comme attribut data
  selectElement[0].responseData = response.serialized_form;

  data.forEach((item) => {
    const $option = $("<option></option>");
    $option.val(item[0]);
    $option.text(item[1]);
    selectElement.append($option);
  });
  return selectElement;
}

function updateValue(element) {
  field = element.val();
  response = element[0].responseData; // Récupération sécurisée

  if (!response) {
    console.log("No response data found");
    return;
  }

  valueElement = createElement(field, response);
  element.closest("tr").find(".condition-value-th").html("");
  element.closest("tr").find(".condition-value-th").html(valueElement);
  if (valueElement.is("select")) {
    valueElement.select2();
  }
}

function createElement(field, serialized_form) {
  let element;
  fieldItem = {};

  $.each(serialized_form, function (indexInArray, valueOfElement) {
    if (valueOfElement.name == field) {
      fieldItem = valueOfElement;
    }
  });

  switch (fieldItem.type) {
    case "CheckboxInput":
      element = document.createElement("input");
      element.type = "checkbox";
      element.checked = true;
      element.onchange = function () {
        if (this.checked) {
          $(this).attr("checked", true);
          $(this).val("on");
        } else {
          $(this).attr("checked", false);
          $(this).val("off");
        }
      };
      element.name = "automation_multiple_condition";
      element.className = "oh-switch__checkbox oh-switch__checkbox";
      const wrapperDiv = document.createElement("div");
      wrapperDiv.className = "oh-switch";
      wrapperDiv.style.width = "30px";
      wrapperDiv.appendChild(element);
      $(element).change();
      element = wrapperDiv;
      break;

    case "Select":
    case "SelectMultiple":
      element = document.createElement("select");
      if (fieldItem.type === "SelectMultiple") {
        element.multiple = true;
      }
      element.onchange = function (event) {
        addSelectedAttr(event);
      };
      if (fieldItem.options) {
        fieldItem.options.forEach((optionValue) => {
          if (optionValue.value) {
            const option = document.createElement("option");
            option.value = optionValue.value;
            option.textContent = optionValue.label;
            element.appendChild(option);
          }
        });
      }
      break;

    case "Textarea":
      element = document.createElement("textarea");
      element.style = `height: 29px !important; margin-top: 5px;`;
      element.className = "oh-input w-100";
      if (fieldItem.max_length) {
        element.maxLength = fieldItem.max_length;
      }
      element.onchange = function (event) {
        $(this).html($(this).val());
      };
      break;
      
    case "TextInput":
    case "EmailInput":
    case "NumberInput":
    default:
      element = document.createElement("input");
      element.type = fieldItem.type === "NumberInput" ? "number" : 
                    fieldItem.type === "EmailInput" ? "email" : "text";
      element.style = `height: 30px !important;`;
      element.className = "oh-input w-100";
      if (fieldItem.max_length) {
        element.maxLength = fieldItem.max_length;
      }
      element.onchange = function (event) {
        $(this).attr("value", $(this).val());
      };
      break;
  }
  
  if (element) {
    element.name = "automation_multiple_condition";
    if (fieldItem.required) {
      element.required = true;
    }
    return $(element);
  }
}

function addSelectedAttr(event) {
  const options = Array.from(event.target.options || []);
  options.forEach((option) => {
    if (option.selected) {
      option.setAttribute("selected", "selected");
    } else {
      option.removeAttribute("selected");
    }
  });
}