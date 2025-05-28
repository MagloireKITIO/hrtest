
const driver = window.driver.js.driver;



var steps = [
    { popover: { title: 'Dashboard', description: 'Activa RH dashboard section' } },
    { element: '#attendance-activity-container', popover: { title: 'View stats', description: '' } },
];

if ($('#settingsMenu').length) {
    steps.push({ element: '#settingsMenu', popover: { title: 'Settings', description: 'Settings configurations' } });
}

if ($('#notificationIcon').length) {
    steps.push({ element: '#notificationIcon', popover: { title: 'Notification', description: 'Notifications section' } });
}

if ($('#multiLanguage').length) {
    steps.push({ element: '#multiLanguage', popover: { title: 'Language', description: 'Multi-Language options' } });
}
if ($('#multCompany').length) {
    steps.push({ element: '#multCompany', popover: { title: 'Multi-Company', description: 'Multi-Company options' } });
}
if ($('#mainNavProfile').length) {
    steps.push({ element: '#mainNavProfile', popover: { title: 'Profile', description: 'Profile and change password options' } });
}
if ($('.oh-card-dashboard').length) {
    steps.push({ element: '#tileContainer .oh-card-dashboard:nth-child(1)', popover: { title: 'Dashboard Tiles', description: 'Activa RH Dashboard Tiles' } });
}
setTimeout(() => {
    if ($('#addAnnouncement').length) {
        steps.push({ element: '#addAnnouncement', popover: { title: 'Add announcement', description: 'Create announcement from dashboard' } });
    }
    if ($('.oh-sidebar__company').length) {
        steps.push({ element: '.oh-sidebar__company:nth-child(1)', popover: { title: 'Company', description: 'Your current company access' } });
    }

}, 1000);
driverObj = driver(

    {
        showProgress: false,
        animate: true,
        showButtons: ['next', 'previous', 'close'],
        steps: steps,


    }
)



function runDriver() {
    // Start driving after checking all steps

    driverObj.drive();
    $.ajax({
        type: "get",
        url: "/driver-viewed?user=" + $(".logged-in[data-user-id]").attr("data-user-id") + "&viewed=dashboard",
        success: function (response) {

        }
    });
}
