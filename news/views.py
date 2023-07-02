from typing import Any, Dict
from django.forms.models import BaseModelForm
from django.http import HttpResponse
from django.views.generic import ListView, DetailView, UpdateView, DeleteView
from requests import request

from .models import Post, Category, BaseRegisterForm, Author, Reply, Comment
from .forms import PostForm, ReplyForm, CommentForm
from .filter import PostFilter
from django.contrib.auth.models import User, Group
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib import messages


@login_required
def upgrade_me(request):
    Author.objects.create(user_author=request.user)
    authors_group = Group.objects.get(name='authors')
    if not request.user.groups.filter(name='authors').exists():
        authors_group.user_set.add(request.user)
    return redirect('/news/')


class PostList(LoginRequiredMixin, ListView):
    model = Post
    ordering = '-date_in'
    template_name = 'news.html'
    context_object_name = 'post_news'
    paginate_by = 5

    def get_context_data(self,
                         **kwargs):  # забираем отфильтрованные объекты переопределяя метод get_context_data у наследуемого класса
        context = super().get_context_data(**kwargs)
        context['filter'] = PostFilter(self.request.GET, queryset=self.get_queryset())  # вписываем фильтр в контекст
        context['categories'] = Category.objects.all()
        context['form'] = PostForm()
        context['is_not_author'] = not self.request.user.groups.filter(name='authors').exists()
        return context

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)  # создаём новую форму, забиваем в неё данные из POST-запроса

        if form.is_valid():  # если пользователь ввёл всё правильно и нигде не ошибся, то сохраняем новый пост
            form.save()

        return super().get(request, *args, **kwargs)


class PostDetailAndCommentCreate(LoginRequiredMixin, CreateView):
    form_class = CommentForm
    template_name = 'onenews.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['post'] = Post.objects.get(pk=self.kwargs['pk'])
        context['comments'] = Comment.objects.filter(post_comment=context['post'], approved=True)
        return context

    def form_valid(self, form):
        object_ = form.save(commit=False)
        object_.post_comment = Post.objects.get(pk=self.kwargs['pk'])
        object_.user_comment = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('post_detail', kwargs={'pk': self.kwargs['pk']})


class PostCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'news.post_add'
    form_class = PostForm
    model = Post
    template_name = 'post_add.html'


class PostUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'news.post_edit'
    form_class = PostForm
    model = Post
    template_name = 'post_edit.html'


# дженерик для удаления поста
class PostDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'news.post_delete'
    model = Post
    template_name = 'post_delete.html'
    queryset = Post.objects.all()
    success_url = '/news/'
    context_object_name = 'post_delete'


class PostSearch(ListView):  # поиск поста
    model = Post
    template_name = 'post_search.html'
    context_object_name = 'post_news'
    paginate_by = 50

    def get_queryset(self):  # получаем обычный запрос
        queryset = super().get_queryset()  # используем наш класс фильтрации
        self.filterset = PostFilter(self.request.GET, queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filterset'] = self.filterset
        return context


class BaseRegisterView(CreateView):
    model = User
    form_class = BaseRegisterForm
    success_url = '/'


class CategoryListView(ListView):
    model = Post
    template_name = 'category_list.html'
    context_object_name = 'category_news_list'

    def get_queryset(self):
        self.category = get_object_or_404(Category, id=self.kwargs['pk'])
        queryset = Post.objects.filter(category=self.category).order_by('-date_in')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_not_subscriber'] = self.request.user not in self.category.subscribers.all()
        context['category'] = self.category
        return context


class CommentCreateView(LoginRequiredMixin, CreateView):  # создание комментария
    model = Comment
    fields = ['content']
    template_name = 'comm_create.html'
    success_url = reverse_lazy('post_detail')

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.post_id = self.kwargs['pk']
        form.instance.parent_id = self.request.POST.get('parent_id', None)
        return super().form_valid(form)


class CommentListView(LoginRequiredMixin, ListView):  # отображения списка комментариев пользователя
    model = Comment
    template_name = 'comm_list.html'
    context_object_name = 'comments'

    def get_queryset(self):
        user = self.request.user
        return Comment.objects.filter(user=user)


class CommentFilterView(LoginRequiredMixin, ListView):  # фильтрации комментариев по постам
    model = Comment
    template_name = 'comm_list.html'
    context_object_name = 'comments'

    def get_queryset(self):
        user = self.request.user
        post_id = self.kwargs['pk']
        return Comment.objects.filter(user=user, post_id=post_id)


class CommentDeleteView(LoginRequiredMixin, DeleteView):  # удаления комментария
    model = Comment
    success_url = reverse_lazy('comm_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Комментарий удален')
        return super().delete(request, *args, **kwargs)


class CommentApproveView(LoginRequiredMixin, DeleteView):  # принятия комментария
    model = Comment
    success_url = reverse_lazy('comm_list')

    def approve(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.approved = True
        self.object.save()
        messages.success(request, 'Комментарий добавлен')
        return super().delete(request, *args, **kwargs)


'''
class ReplyCreate(LoginRequiredMixin,PermissionRequiredMixin, CreateView):
    permission_required = 'rpg.comm_create'
    form_class = ReplyForm
    model = Reply
    template_name = 'comm_create.html'

    def form_valid(self, form):
        reply = form.save(commit=False)
        if self.request.method == 'POST':
            pk = self.request.path.split('/')[-3]
            sender = self.request.user
            reply.post = Post.objects.get(id=pk)
            reply.sender = User.objects.get(username=sender)
        reply.save()
        return super().form_valid(form)

    def get_success_url(self):
        url = '/'.join(self.request.path.split('/')[0:-2])
        return url


class Replies(PermissionRequiredMixin, ListView):
    permission_required = 'rpg.comm_post'
    model = Reply
    template_name = 'comm_post.html'
    context_object_name = 'replies'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(post__author_id=self.request.user.id)
'''


@login_required
def subscribe(request, pk):
    user = request.user
    category = Category.objects.get(id=pk)
    category.subscribers.add(user)
    message = 'вы подписались на категорию: '
    return render(request, 'subscribe.html', {'category': category, 'message': message})


@login_required
def unsubscribe(request, pk):
    user = request.user
    category = Category.objects.get(id=pk)
    category.subscribers.remove(user)
    message = 'отписка от категории: '
    return render(request, 'subscribe.html', {'category': category, 'message': message})


'''
def add_comment(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            return redirect('news', pk=post.pk)
    else:
        form = CommentForm()
    return render(request, 'comment_create.html', {'form': form})
'''
