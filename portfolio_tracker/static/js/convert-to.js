$(function () {

  $('body').on("click", ".convert-text", function () {
    var $box = $(this),
      convertTo = $box.attr("data-convert-to");

    if ($box.hasClass("active")) {
      return true;
    }

    var newTextBox = "";
    if (convertTo == "textarea") {
      newTextBox += '<textarea class="form-control convert-data" name="' + $box.attr("data-name") + '">';
      newTextBox += $box.find(".convert-data").text();
      newTextBox += "</textarea>";
    }

    $box.addClass("active").empty();

    $box = $box.append("<form></form>").find("form");
    $box.append(newTextBox);

    $box.append(`
      <div class="position-right">
        <button class="btn btn-primary btn-sm submit" type="button">` + trans.btn_save + `</button>
      </div>
      `);
    $box.find('textarea').focus();

    $box.on("click", ".submit", function () {
      var $box = $(this).closest(".convert-text"),
        $form = $box.find("form"),
        url = $box.attr("data-url"),
        posting = $.post(url, $form.serialize());

      $form.closest('.modal').attr('data-pre-need-update', true);

      posting.done(function (data) {
        $box.empty().append(`<span class="convert-data">` +
          $form.find(".convert-data").val() + `</span>`);
      });
    });

  });
})
