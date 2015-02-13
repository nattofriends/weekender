function Weekender() {
    this.dateTarget = $('#date');

    // There is no cancelLoading...
    this.cancelLoading = $('.js-cancel-loading');
    this.info = $('.js-info');
    this.error = $('.js-error');

    this.xhr = undefined;

    this.fareResult = new FareResult($('.js-result'));

    this.cancelLoading.click($.proxy(this.onCancelLoading, this));

    $('.js-search').click($.proxy(this.onSet, this));

    var pickerHolder = $('.picker-holder');

    var picker = this.dateTarget.pickadate({
        disable: [
            1, 2, 3, 4, 5,
            {from: [0, 0, 0], to: true}
        ],
        format: 'yyyymmdd',
        firstDay: true,
        today: false,
        clear: false,
        close: false,
    }).pickadate('picker');  // What's picker?
   
    picker.open();
    
    // Unbind the close handler completely
    picker.close = function (_) { return picker; };
    
    // Move the element over.  
    picker.$root.detach().appendTo(pickerHolder);
};

Weekender.prototype.onSet = function (ctx) {
    var dateValue = this.dateTarget.val();

    if (dateValue === '') {
        return;
    }

    this.info.removeClass('hidden');
    this.fareResult.clear();

    this.xhr = $.ajax({
        url: 'flights',
        data: {selected: dateValue},
    })
    .done($.proxy(this.onFlightResult, this))
    .fail($.proxy(this.onError, this));
};

Weekender.prototype.onError = function (xhr, textStatus, errorThrown) {
    this.hideInfo_();

    this.error.removeClass('hidden');
    setTimeout($.proxy(
        function () { this.error.addClass('hidden'); },
        this
    ),
    1500);
};

Weekender.prototype.onFlightResult = function (data) {
    this.hideInfo_();

    var begin = $.map(data['begin'], function (val, idx) {
        return new Fare(val);
    });

    var end = $.map(data['end'], function (val, idx) {
        return new Fare(val);
    });

    this.fareResult.render(begin, end);
};

Weekender.prototype.onCancelLoading = function (data) {
    this.hideInfo_();

    if (this.xhr !== undefined) {
        this.xhr.abort();
    }
};

Weekender.prototype.hideInfo_ = function () {
    this.info.addClass('hidden');
};


function Fare(fare) {
    fields = ['origin', 'destination', 'departDate', 'isEarly', 'departTime', 'arriveTime', 'flightNo', 'fare'];

    $.each(fields, $.proxy(function (idx, val) {
        this[fields[idx]] = fare[idx];
    }, this));
}

Fare.prototype.urlBase = "https://www.gstatic.com/flights/airline_logos/16px/%s.png"

Fare.prototype.render = function (container) {
    this.container = container;

    var datetime = container.find('.js-date-time');
    var origin = container.find('.js-origin');
    var destination = container.find('.js-destination')
    var flight = container.find('.js-flight');
    var fare = container.find('.js-fare');

    datetime.html(sprintf("%s %s - %s", this.departDate, this.departTime, this.arriveTime));
    origin.html(this.origin);
    destination.html(this.destination);
    flight.html(this.flightNo);
    fare.html(sprintf("$%s", this.fare));

    return this;
};  

Fare.prototype.hide = function () {
    this.container.addClass('hidden');
};

Fare.prototype.show = function (clickHandler) {
    this.container.removeClass('hidden js-other-fare');
    this.container.addClass('strong');

    this.container.click(clickHandler);
};

Fare.prototype.addClass = function (class_) {
    this.container.addClass(class_);
};

Fare.prototype.toggleEarly = function () {
    if (this.isEarly) {
        this.container.toggleClass('strikethrough');
    }
};

Fare.prototype.clear = function () {
    this.container.detach();
};

function FareResult(container) {
    this.container = container;

    this.title = container.find('.js-title');
    this.table = container.find('.js-table');
    this.row = container.find('.js-row');
    this.filterEarly = container.find('.js-filter-early');

    this.filterEarly.change($.proxy(this.onFilterEarly, this));

    this.rows = [];
}

FareResult.prototype.render = function (begin, end) {
    this.container.removeClass('hidden');

    beginRows = $.map(begin, $.proxy(function (val, idx) {
        val.render(this.row.clone());
        this.table.append(val.container);
        val.addClass('success js-other-fare');
        return val;
    }, this));

    endRows = $.map(end, $.proxy(function (val, idx) {
        val.render(this.row.clone());
        this.table.append(val.container);
        val.addClass('warning js-other-fare');
        return val;
    }, this));

    beginRows[0].show($.proxy(function () {
        this.container.find('.success').filter('.js-other-fare').toggleClass('hidden');
    }, this));
    endRows[0].show($.proxy(function () {
        this.container.find('.warning').filter('.js-other-fare').toggleClass('hidden');
    }, this)); 

    var cheapest = beginRows[0].fare + endRows[0].fare;
    this.title.html(sprintf("Go home for $%s!", cheapest));

    this.rows = beginRows.slice(0).concat(endRows);
};

FareResult.prototype.clear = function () {
    this.container.addClass('hidden');
    this.filterEarly.prop('checked', false);

    $.each(this.rows, function (idx, val) {
        val.clear();
    });
};

FareResult.prototype.onFilterEarly = function () {
    $.each(this.rows, function (idx, val) {
        val.toggleEarly();
    });
};
