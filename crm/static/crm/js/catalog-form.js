document.addEventListener("DOMContentLoaded", function () {
    const groupToggles = document.querySelectorAll(".product-group-toggle");

    function syncGroupToggle(groupId) {
        const groupToggle = document.querySelector('.product-group-toggle[data-product-group="' + groupId + '"]');
        const groupItems = document.querySelectorAll('input[data-product-group-item="' + groupId + '"]');
        const checkedItems = Array.from(groupItems).filter(function (item) {
            return item.checked;
        });

        groupToggle.checked = groupItems.length > 0 && checkedItems.length === groupItems.length;
        groupToggle.indeterminate = checkedItems.length > 0 && checkedItems.length < groupItems.length;
    }

    groupToggles.forEach(function (groupToggle) {
        const groupId = groupToggle.dataset.productGroup;
        const groupItems = document.querySelectorAll('input[data-product-group-item="' + groupId + '"]');
        const groupToggleLabel = groupToggle.closest(".product-picker-group-toggle");

        syncGroupToggle(groupId);

        groupToggleLabel.addEventListener("click", function (event) {
            event.stopPropagation();
        });

        groupToggle.addEventListener("click", function (event) {
            event.stopPropagation();
        });

        groupToggle.addEventListener("change", function () {
            groupItems.forEach(function (item) {
                item.checked = groupToggle.checked;
            });
            syncGroupToggle(groupId);
        });

        groupItems.forEach(function (item) {
            item.addEventListener("change", function () {
                syncGroupToggle(groupId);
            });
        });
    });
});
