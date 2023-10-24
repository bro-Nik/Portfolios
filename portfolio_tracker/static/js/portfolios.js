const $modalsBox = $('#Modals');

$(function () {

  // Check All
  $("body").on("change", ".check-all", function () {
    var $form = $(this).closest("form");
    $form.find(".to-check").prop("checked", $(this).is(":checked")).trigger("change");
  });

  // Decheck All
  $("body").on("click", ".decheck-all", function () {
    var $form = $(this).closest("form");
    $form.find(".to-check").prop("checked", false).trigger("change");
  });

  // Check Count
  $("body").on("change", ".to-check", function () {
    var $form = $(this).closest("form"),
      checked_count = $form.find(".to-check:checked").length,
      all_count = $form.find(".to-check").length,
      $box_actions = $form.find(".sticky-bottom.actions");

    if (checked_count > 0) {
      $box_actions.addClass("active");
    } else {
      $box_actions.removeClass("active");
    }
    $box_actions.find(".checks-count").text(checked_count + " / " + all_count);
    $form.find(".check-all").prop("checked", checked_count > 0);
  });

  // Action
  $("body").on("click", ".action", function () {
    var $btn = $(this),
      checked = [];

    // If button not in form
    if ($btn.attr("data-form")) {
      var $form = $($btn.attr("data-form"));
    } else {
      var $form = $btn.closest("form");
    }

    // If info not in main form
    if ($btn.attr("data-form-info")) {
      var info = $($btn.attr("data-form-info")).serializeArray();
    } else {
      var info = $form.serializeArray();
    }

    if ($btn.attr("data-id")) {
      checked.push($btn.attr("data-id"));
    } else {
      $form.find(".to-check:checked").each(function () {
        checked.push($(this).val());
      });
    }

    var data = {
      action: $btn.attr("data-action"),
      info: info,
      ids: checked,
    };

    var $modal = $btn.closest('.modal');
    $modal.attr('data-pre-need-update', true);

    $.ajax({
      type: "POST",
      url: $form.attr("action"),
      data: JSON.stringify(data),
      contentType: "application/json; charset=utf-8",
    }).done(function (response) {
      if(response.redirect) {
        window.location.href = response.redirect;
      } else if ($btn.attr('data-this-need-update')) {
        LoadToModal($modal.attr('id'), $modal.attr("data-url"), true);
      } else {
        setTimeout(PageUpdate, 500, $modal);
      }
    });
  });

  // Modals
  //
  // Open modal to confirm
  $("body").on("click", ".open-modal-confirmation", function () {
    var $modal = $("#ModalConfirmation"),
      $btn = $(this);

    if ($btn.attr("data-form")) {
      $modal.find(".action").attr("data-form", $btn.attr("data-form"));
    } else {
      $modal.find(".action").attr("data-form", "#" + $btn.closest("form").attr("id"));
    }

    // if modal then update
    var pre_modal_id = $btn.closest(".modal").attr("id");
    if (pre_modal_id) {
      $modal.attr("data-pre-modal-id", pre_modal_id);
    } else {
      $modal.removeAttr("data-pre-modal-id");
    }
    var pre_need_clean = $btn.attr("data-pre-need-clean") || false;
    $modal.attr("data-pre-need-clean", pre_need_clean);

    // to modal action
    var title = $btn.attr("data-title"),
      action = $btn.attr("data-action"),
      id = $btn.attr("data-id") || "",
      text = $btn.attr("data-text") || "";
    $modal.find(".modal-title").text(title);
    $modal.find(".modal-text").text(text);
    $modal.find(".action").attr("data-action", action);
    $modal.find(".action").attr("data-id", id);
    $modal.modal({backdrop: false}).modal("show");
  });

  $("body").on("click", ".open-modal", function () {
    var modal_id = $(this).attr("data-modal-id"),
      url = $(this).attr("data-url"),
      pre_modal_id = $(this).closest('.modal').attr('id');
    if ($(this).hasClass('not-update')) {
      pre_modal_id = false;
    }
    LoadToModal(modal_id, url, false, pre_modal_id);
  });

  // Close modal
  $("body").mousedown(function (e) {
    if ($(e.target).is(".modal")) {
      $(e.target).modal("hide");
    }
  });


  // Open Modal
  $("body").on("show.bs.modal", ".modal", function () {
    var $modal = $(this);

    $modal.css("height", $(window).height());
    var $active_modals = $("body").find(".modal.show"),
      z_index = parseInt($modal.css("z-index"));

    $active_modals.each(function () {
      if ($(this).index() !== $modal.index()) {
        var this_z_index = parseInt($(this).css("z-index"));
        if ($modal.find(".modal-fullscreen").length) {
          $(this).find(".modal-close-label").css("top", "+=60");
        }
        if ((this_z_index) => z_index) {
          z_index = this_z_index + 1;
        }
      }
    });
    $modal.css("z-index", z_index);

    // Fade
    if (!$modal.find(".modal-fullscreen").length) {
      $("body").append(
        '<div class="modal-backdrop fade show" style="z-index: ' + (z_index - 1) + ';"></div>'
      );
    }
  });

  $("body").on("shown.bs.modal", function () {
    var $modal = $(this);
    $("body .modal-backdrop").css("z-index", parseInt($modal.css("z-index")) - 1);

    UpdateFocus($modal);
  });

  // Close Modal
  $("body").on("hide.bs.modal", ".modal", function () {
    var $modal = $(this);

    if (!$(".modal.show").length > 1) {
      return false;
    }

    var z_index = parseInt($modal.css("z-index"));
    var max_z_index = 0;

    $("body").find(".modal.show").each(function () {
        var this_z_index = parseInt($(this).css("z-index"));
        if (this_z_index !== z_index && this_z_index > max_z_index) {
          max_z_index = this_z_index;
        }
      });

    if ($modal.find(".modal-fullscreen").length) {
      $("body").find(".modal.show").each(function () {
        if ($(this).index() !== $modal.index()) {
          $(this).find(".modal-close-label").css("top", "-=60");
        }
      });
    }
  });

  $("body").on("hidden.bs.modal", ".modal", function () {
    var $modal = $(this);
    // Fade
    if (!$modal.find(".modal-fullscreen").length) {
      $("body .modal-backdrop").eq(-1).remove();
    } else {
      $modal.find('.modal-body').empty();
    }
  });

  $('body').on('hide.bs.modal', '.modal', function () {
    var $modal = $(this);
    if ($modal.attr('id') != 'ModalConfirmation' && !$modal.hasClass('not-update')) {
      PageUpdate($modal);
    }
  })

  $('body').on("click", ".load-page-or-modal", function () {
    var modal_id = $(this).closest(".modal").attr("id"),
      url = $(this).attr("data-url");

    if (modal_id) {
      LoadToModal(modal_id, url);
    } else {
      LoadToPage(url);
    }
  });

  // Form
  $('body').on("submit", function(event) {
    var $form = $(event.target),
      $modal = $form.closest(".modal");

    if ($modal.length) {
      event.preventDefault();

      var posting = $.post($form.attr("data-url"), $form.serialize());

      posting.done(function (data) {
        $modal.attr('data-pre-need-update', true)
        $modal.modal("hide");
      });
    }
  });

  // Show more content
  $('body').on('click', '.show-more', function () {
    $(this).next('.show-more-content').slideToggle(500);
  })

  // Paste into input
  $('body').on('click', '.paste-into-input', function () {
    var $input = $(this).closest('div').find('input');
    $input.val($(this).data('value')).trigger('input');
  })

})

// Load to Page
function LoadToPage(url) {
  if (!url) {
    url = $(location).attr('href');
    url += (url.indexOf("?") > 0 ? "&" : "?") + "only_content=true";
  }
  $('#content').load(url, function () {
    UpdateScripts($('#content'));
    UpdateFocus($('#content'));
  });

}

// Load to Modal
function LoadToModal(modal_id, url, pre_need_update, pre_modal_id) {
  var $modal = $("#" + modal_id);

  // нужно для обновления контента в модульном
  if ($modal.length) {
    // load only content
    if ($modal.find(".modal-fullscreen").length) {
      var $loadIn = $modal.find(".modal-body").empty();
      url += (url.indexOf("?") > 0 ? "&" : "?") + "only_content=true";
    } else {
      var $loadIn = $modal.empty();
    }
  } else {
    // create and load full modal
    var $loadIn = $modal = $('<div>', {
      id: modal_id,
      class: 'modal fade',
      tabindex: '-1'
    })
    .attr('aria-hidden', 'false')
    .appendTo($modalsBox);
  }
  
  $modal.attr("data-pre-need-update", pre_need_update || false);
  if (pre_modal_id) {
    $modal.attr("data-pre-modal-id", pre_modal_id);
  }

  $loadIn.load(url, function () {
    UpdateScripts($modal);
    UpdateSmartSelects($modal);
    $modal.modal({
      backdrop: false,
      keyboard: true,
    });
    $modal.attr("data-url", url);
    if (!$modal.hasClass("show")) {
      $modal.modal("show");
    } else {
      UpdateFocus($modal);
    }
  });
}

function PageUpdate($modal) {
  var this_need_update = $modal.attr("data-this-need-update"),
    pre_need_update = $modal.attr("data-pre-need-update"),
    pre_need_clean = $modal.attr("data-pre-need-clean"),
    pre_modal_id = $modal.attr("data-pre-modal-id");

  if (pre_need_clean == 'true') {
    $('#' + pre_modal_id).attr('data-pre-need-update', true);
    $('#' + pre_modal_id).modal('hide');
  } else if (pre_need_update == 'true') {
    if (pre_modal_id) {
      LoadToModal(pre_modal_id, $("#" + pre_modal_id).attr("data-url"), true);
    } else {
      LoadToPage();
    }
  }
}

// Focus
function UpdateFocus($element = $("body")) {
  if ($element.find('.focus').length) {
    $element.find('.focus').focus();
  } else {
    $element.find(".search-input").focus();
  }
}

// Update Page
function UpdateScripts($element) {
  UpdateSmartSelects($element);
  StickyBottomActionsUpdate($element);
  UpdateTables($element);
  CreateConvertTo($element);
}


// Update Table
function UpdateTables($element = $("body")) {
  $element.find(".bootstrap-table").bootstrapTable({
    formatSearch() {
      return trans.search;
    },
    formatNoMatches() {
      return trans.nothing_found;
    },
    formatLoadingMessage: function() {
        return trans.loading;
    },
  })
  // Sort
  .on('click', '.th-inner.sortable', function () {
    var tab_name = $(this).closest('table').data('name'),
      field = $(this).parent().data('field'),
      sort_order = $(this).hasClass('desc') ? 'asc' : 'desc',
      url = $(this).closest('table').data('sort-url');

    if (tab_name && field && sort_order && url) {
      url += '?tab_name=' + tab_name + '&field=' + field + '&sort_order=' + sort_order;
      $.get(url)
    }
  })
}

// Sticky Bottom Actions
function StickyBottomActionsUpdate($element = $("body")) {

  if ($element.find('form').length > 1) {
    $element.find('form').each(function () {
      CreateStickyBottomActions($(this));
    })
  } else {
    CreateStickyBottomActions($element);
  }
}

function CreateStickyBottomActions($element) {
  var $content = $(`
    <div class="sticky-bottom actions">
      <div class="col-12">
        <div class="bg-white h-100 d-flex gap-2 align-items-center align-items-center">
          <span class="ms-5">` + trans.selected + `</span>
          <span class="checks-count"></span>
          <a class="ms-3 decheck-all">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8 2.146 2.854Z"/></svg>
          </a>
          <div class="vr my-3"></div>
          <div class="buttons"></div>
        </div>
      </div>
    </div>
  `);
  var stickyBottomButtons = $element.find(".sticky-bottom-buttons");
  if (stickyBottomButtons.length) {
    $content.find('.buttons').append(stickyBottomButtons.children());
    stickyBottomButtons.parent().append($content);
    stickyBottomButtons.remove();
  }
}

StickyBottomActionsUpdate();
UpdateTables();
CreateConvertTo();
$('body .fade').addClass('show');
UpdateFocus();
