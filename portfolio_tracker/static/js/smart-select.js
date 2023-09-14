function UpdateSmartSelects($element = $("body")) {
  $element.find('select').each(function() {
    if ($(this).hasClass('visually-hidden')) {
      return false;
    }

    var $select = $(this),
      selectedOption = $select.find('option:selected'),
      selectClass = $(this).attr('data-class');

    $select.addClass('visually-hidden');
    $select.wrap('<div class="smart-select-box"></div>');
    $('<div>', {
        class: 'smart-select' + (selectClass ? ' ' + selectClass : ''),
        text: selectedOption.length ? selectedOption.text() : $select.attr('data-placeholder') || ' '
    }).insertAfter($select);


    var selectHead = $select.next('.smart-select');
    $('<div>', {
        class: 'smart-select__list'
    }).insertAfter(selectHead);

    var selectList = selectHead.next('.smart-select__list');
    selectList.slideUp(0);

    $select.on('focus', function() {
      $(this).trigger('blur');
      selectHead.trigger('click');
    })

    selectHead.on('click', function() {
      if (!$(this).hasClass('on')) {
        $(this).addClass('on');
        
        // load options
        if ($select.attr('data-url')) {
          GetOptions($select);
        } else {
          GenerateSelect($select)
        }
      } else {
        $(this).removeClass('on');
        selectList.slideUp(50);
      }
    });
  });
}

function GenerateSelect($select) {
  var options_list = $select.parent().find('.smart-select__item').length,
    selectList = $select.next('.smart-select').next('.smart-select__list');

  if (!options_list) {
    var selectOption = $select.find('option'),
      selectOptionLength = selectOption.length;

    for (let i = 0; i < selectOptionLength; i++) {
      if (selectOption.eq(i).val() && selectOption.eq(i).text()) {
        var is_selected = selectOption.eq(i).prop('selected') ? ' selected' : '';
        $('<div>', {
          class: 'smart-select__item' + is_selected,
          html: $('<span>', {
            text: selectOption.eq(i).text()
          })
        })
        .attr('data-value', selectOption.eq(i).val())
        .appendTo(selectList);
      }
    }
  }
  ClickInSelect($select);
  selectList.slideDown(50);
}

function GetOptions($select) {
  var selectedOptionValue = $select.find('option:selected').val();
  $.get($select.attr('data-url'), function (data) {
    data = $.parseJSON(data);

    $select.empty().append($('<option>', {value: '', text: ''}));

    for (let i = 0; i < data.length; i++) {
      var $newOption = $('<option>', {
        value: data[i].value,
        text: data[i].text
      })

      $select.append($newOption);
      if (data[i].value == selectedOptionValue) {
        $newOption.attr('selected', 'selected');
      }
    }
    $select.parent().find('.smart-select__list').empty();
    GenerateSelect($select);
    ClickInSelect($select);
  })
}

function ClickInSelect($select){
  var selectList = $select.next('.smart-select').next('.smart-select__list'),
    selectItem = selectList.find('.smart-select__item'),
    selectHead = $select.next('.smart-select');

  selectItem.on('click', function() {
    var chooseItem = $(this).data('value');

    // selected class
    selectItem.removeClass('selected');
    $(this).addClass('selected');

    $select.val(chooseItem).attr('selected', 'selected');
    selectHead.text($(this).find('span').text());

    selectList.slideUp(50);
    selectHead.removeClass('on');
  });

}
