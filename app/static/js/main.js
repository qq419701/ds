// Dropdown toggle
document.addEventListener('click', function(e) {
    // Close all dropdowns
    document.querySelectorAll('.dropdown-content.show').forEach(function(el) {
        if (!el.parentElement.contains(e.target)) {
            el.classList.remove('show');
        }
    });
});

function toggleDropdown(btn) {
    var content = btn.nextElementSibling;
    document.querySelectorAll('.dropdown-content.show').forEach(function(el) {
        if (el !== content) el.classList.remove('show');
    });
    content.classList.toggle('show');
}

// Modal functions
function showModal(id) {
    document.getElementById(id).classList.add('show');
}

function hideModal(id) {
    document.getElementById(id).classList.remove('show');
}

// 显示订单详情弹窗
function showOrderDetail(orderId) {
    const modal = document.getElementById('orderModal');
    const content = document.getElementById('orderDetailContent');
    
    if (!modal || !content) {
        alert('❌ 弹窗元素未找到');
        return;
    }
    
    // 显示弹窗和加载状态
    modal.style.display = 'block';
    content.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="loading-spinner"></div><p>加载中...</p></div>';
    
    // 加载订单详情
    fetch(`/order/${orderId}/detail-html`)
        .then(res => res.text())
        .then(html => {
            content.innerHTML = html;
        })
        .catch(err => {
            content.innerHTML = '<div style="text-align: center; padding: 40px; color: #ff4d4f;">❌ 加载失败</div>';
            console.error('加载订单详情失败:', err);
        });
}

// 关闭订单详情弹窗
function closeOrderModal() {
    const modal = document.getElementById('orderModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// 点击弹窗外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('orderModal');
    if (modal && event.target == modal) {
        closeOrderModal();
    }
}

// AJAX helper
function apiPost(url, data) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(function(r) { return r.json(); });
}

// Notify success
function notifySuccess(orderId) {
    if (!confirm('确认通知京东该订单充值成功？')) return;
    fetch(`/order/${orderId}/notify-success`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        alert(data.success ? '✅ ' + data.message : '❌ ' + data.message);
        if (data.success) location.reload();
    })
    .catch(err => {
        console.error('通知成功失败:', err);
        alert('❌ 操作失败');
    });
}

// Notify refund
function notifyRefund(orderId) {
    if (!confirm('确认通知京东该订单已退款？')) return;
    fetch(`/order/${orderId}/notify-refund`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        alert(data.success ? '✅ ' + data.message : '❌ ' + data.message);
        if (data.success) location.reload();
    })
    .catch(err => {
        console.error('通知退款失败:', err);
        alert('❌ 操作失败');
    });
}

// Agiso deliver
function agisoDeliver(orderId) {
    if (!confirm('确认使用阿奇索自动发货？')) return;
    fetch(`/order/${orderId}/agiso-deliver`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        alert(data.success ? '✅ ' + data.message : '❌ ' + data.message);
        if (data.success) location.reload();
    })
    .catch(err => {
        console.error('阿奇索发货失败:', err);
        alert('❌ 操作失败');
    });
}

// Debug functions - 自助联调
function debugSuccess(orderId) {
    if (!confirm('⚠️ 自助联调：标记订单为充值成功？\n\n此操作不会触发京东回调，仅用于测试。')) return;
    fetch(`/order/${orderId}/debug-success`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        alert(data.success ? '✅ ' + data.message : '❌ ' + data.message);
        if (data.success) location.reload();
    })
    .catch(err => {
        console.error('自助联调失败:', err);
        alert('❌ 操作失败');
    });
}

function debugProcessing(orderId) {
    if (!confirm('⚠️ 自助联调：标记订单为充值中？\n\n此操作不会触发京东回调，仅用于测试。')) return;
    fetch(`/order/${orderId}/debug-processing`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        alert(data.success ? '✅ ' + data.message : '❌ ' + data.message);
        if (data.success) location.reload();
    })
    .catch(err => {
        console.error('自助联调失败:', err);
        alert('❌ 操作失败');
    });
}

function debugFailed(orderId) {
    if (!confirm('⚠️ 自助联调：标记订单为充值失败？\n\n此操作不会触发京东回调，仅用于测试。')) return;
    fetch(`/order/${orderId}/debug-failed`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        alert(data.success ? '✅ ' + data.message : '❌ ' + data.message);
        if (data.success) location.reload();
    })
    .catch(err => {
        console.error('自助联调失败:', err);
        alert('❌ 操作失败');
    });
}

// Card delivery modal
function showCardModal(orderId, quantity) {
    var html = '<div class="modal-title">🚚 卡密发货</div>';
    html += '<p class="mb-4">请输入 ' + quantity + ' 组卡密信息：</p>';
    for (var i = 0; i < quantity; i++) {
        html += '<div class="form-row mb-2">';
        html += '<div class="form-group"><label>卡号 ' + (i + 1) + '</label>';
        html += '<input type="text" class="form-control card-no" placeholder="请输入卡号"></div>';
        html += '<div class="form-group"><label>密码 ' + (i + 1) + '</label>';
        html += '<input type="text" class="form-control card-pwd" placeholder="请输入密码"></div>';
        html += '</div>';
    }
    html += '<div class="modal-footer">';
    html += '<button class="btn" onclick="hideModal(\'cardModal\')">取消</button>';
    html += '<button class="btn btn-primary" onclick="submitCards(' + orderId + ', ' + quantity + ')">提交发货</button>';
    html += '</div>';

    var modal = document.getElementById('cardModal');
    if (modal) {
        modal.querySelector('.modal').innerHTML = html;
        showModal('cardModal');
    }
}

function submitCards(orderId, quantity) {
    var cardNos = document.querySelectorAll('.card-no');
    var cardPwds = document.querySelectorAll('.card-pwd');
    var cards = [];
    for (var i = 0; i < quantity; i++) {
        var no = cardNos[i].value.trim();
        var pwd = cardPwds[i].value.trim();
        if (!no || !pwd) {
            alert('请填写完整的卡密信息');
            return;
        }
        cards.push({ cardNo: no, cardPwd: pwd });
    }
    apiPost('/order/deliver-card/' + orderId, { cards: cards }).then(function(res) {
        alert(res.message);
        if (res.success) {
            hideModal('cardModal');
            location.reload();
        }
    });
}

// Test notification
function testNotification(shopId, notifyType) {
    apiPost('/shop/test-notification', { shop_id: shopId, notify_type: notifyType }).then(function(res) {
        alert(res.message);
    });
}

// Resend notification
function resendNotification(logId) {
    if (!confirm('确认重新发送通知？')) return;
    apiPost('/notification/resend', { log_id: logId }).then(function(res) {
        alert(res.message);
        if (res.success) location.reload();
    });
}

// ==================== 卡密相关函数 ====================

// 生成随机卡密
function generateRandomCards(quantity) {
    if (!quantity) {
        const form = document.getElementById('cardForm');
        if (form) {
            quantity = parseInt(form.dataset.quantity);
        }
    }
    
    if (!quantity) {
        alert('❌ 无法获取卡密数量');
        return;
    }
    
    for (let i = 0; i < quantity; i++) {
        // 生成10-20位随机卡号
        const cardNoLength = 10 + Math.floor(Math.random() * 11);
        const cardNo = generateRandomNumber(cardNoLength);
        
        // 生成4-12位随机密码
        const cardPwdLength = 4 + Math.floor(Math.random() * 9);
        const cardPwd = generateRandomPassword(cardPwdLength);
        
        const cardNoInput = document.querySelector(`input[name="cardNo_${i}"]`);
        const cardPwdInput = document.querySelector(`input[name="cardPwd_${i}"]`);
        
        if (cardNoInput && cardPwdInput) {
            cardNoInput.value = cardNo;
            cardPwdInput.value = cardPwd;
        }
    }
    
    alert('✅ 已生成 ' + quantity + ' 组随机卡密');
}

// 生成随机数字
function generateRandomNumber(length) {
    let result = '';
    for (let i = 0; i < length; i++) {
        result += Math.floor(Math.random() * 10);
    }
    return result;
}

// 生成随机密码（数字+字母）
function generateRandomPassword(length) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

// 清空所有卡密
function clearAllCards(quantity) {
    if (!quantity) {
        const form = document.getElementById('cardForm');
        if (form) {
            quantity = parseInt(form.dataset.quantity);
        }
    }
    
    if (confirm('确认清空所有卡密输入？')) {
        for (let i = 0; i < quantity; i++) {
            const cardNoInput = document.querySelector(`input[name="cardNo_${i}"]`);
            const cardPwdInput = document.querySelector(`input[name="cardPwd_${i}"]`);
            if (cardNoInput && cardPwdInput) {
                cardNoInput.value = '';
                cardPwdInput.value = '';
            }
        }
    }
}

// 提交卡密
function submitCards(event) {
    event.preventDefault();
    
    const form = event.target;
    const quantity = parseInt(form.dataset.quantity);
    const orderId = parseInt(form.dataset.orderId);
    
    if (!quantity || !orderId) {
        alert('❌ 无法获取订单信息');
        return;
    }
    
    const cards = [];
    const usedCardNos = new Set();
    const usedCardPwds = new Set();
    
    // 收集所有卡密
    for (let i = 0; i < quantity; i++) {
        const cardNo = document.querySelector(`input[name="cardNo_${i}"]`).value.trim();
        const cardPwd = document.querySelector(`input[name="cardPwd_${i}"]`).value.trim();
        
        // 检查是否为空
        if (!cardNo || !cardPwd) {
            alert(`❌ 第 ${i+1} 组卡密未填写完整`);
            return;
        }
        
        // 检查是否重复
        if (usedCardNos.has(cardNo)) {
            alert(`❌ 第 ${i+1} 组的卡号已经被使用`);
            return;
        }
        
        if (usedCardPwds.has(cardPwd)) {
            alert(`❌ 第 ${i+1} 组的密码已经被使用`);
            return;
        }
        
        usedCardNos.add(cardNo);
        usedCardPwds.add(cardPwd);
        
        cards.push({
            cardNo: cardNo,
            cardPwd: cardPwd
        });
    }
    
    // 提交到后端
    fetch('/order/' + orderId + '/save-cards', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cards: cards})
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('✅ ' + data.message);
            // 重新加载订单详情，而不是刷新整个页面
            showOrderDetail(orderId);
        } else {
            alert('❌ ' + data.message);
        }
    })
    .catch(err => {
        console.error('提交卡密失败:', err);
        alert('❌ 提交失败');
    });
}
